import re
import sqlite3
import zipfile
from pathlib import Path
from unittest.mock import AsyncMock, patch

import pytest
from aiogram.types import CallbackQuery

from app.handlers.files import delete_contact_noop
from app.keyboards import (
    delete_contact_result_menu,
    delete_contact_selection_menu,
)
from app.locales import (
    DELETE_CONTACT_MESSAGES,
    DELETE_CONTACT_SELECT_PROMPT,
    ENTER_DELETE_CONTACT_PROMPT,
)
from app.services.delete_contact import (
    ContactItem,
    delete_session_contacts,
    fetch_input_contacts,
    fetch_session_contacts,
    process_delete_contacts,
)


def _create_session(path: Path) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    with sqlite3.connect(path) as conn:
        conn.execute("CREATE TABLE version (number integer primary key)")
        conn.execute(
            "CREATE TABLE sessions (dc_id integer, server_address text, port integer, auth_key blob)"
        )
        conn.execute(
            "INSERT INTO sessions VALUES (1, '127.0.0.1', 80, ?)",
            (b"\x01" * 256,),
        )
        conn.commit()
    return path


@pytest.fixture
def dummy_session(tmp_path: Path) -> Path:
    return _create_session(tmp_path / "test.session")


@pytest.mark.asyncio
async def test_fetch_session_contacts(dummy_session: Path):
    mock_client = AsyncMock()
    mock_client.is_user_authorized.return_value = True

    class DummyUser:
        id = 1001
        first_name = "John"
        last_name = "Doe"
        phone = "1234567890"

    class DummyContact:
        user_id = 1001

    class DummyContactsRes:
        def __init__(self):
            self.users = [DummyUser()]
            self.contacts = [DummyContact()]

    mock_client.side_effect = lambda req: DummyContactsRes()

    with patch("telethon.TelegramClient", return_value=mock_client):
        res = await fetch_session_contacts(dummy_session, [(123, "hash")])

    assert len(res) == 1
    assert res[0].user_id == 1001
    assert res[0].first_name == "John"
    assert res[0].last_name == "Doe"
    assert res[0].phone == "1234567890"


@pytest.mark.asyncio
async def test_delete_session_contacts(dummy_session: Path):
    mock_client = AsyncMock()
    mock_client.is_user_authorized.return_value = True
    request_names: list[str] = []

    class DummyUser:
        id = 1001
        first_name = "John"
        last_name = "Doe"
        phone = "1234567890"

    class DummyContact:
        user_id = 1001

    class DummyContactsRes:
        def __init__(self) -> None:
            self.users = [DummyUser()]
            self.contacts = [DummyContact()]

    def handle_request(request):
        request_name = type(request).__name__
        request_names.append(request_name)
        if request_name == "GetContactsRequest":
            return DummyContactsRes()
        return True

    mock_client.side_effect = handle_request

    with patch("telethon.TelegramClient", return_value=mock_client):
        res = await delete_session_contacts(
            dummy_session, [(123, "hash")], target_user_ids=[1001, 1002]
        )

    assert res is True
    assert request_names == ["GetContactsRequest", "DeleteContactsRequest"]


@pytest.mark.asyncio
async def test_delete_session_contacts_does_not_use_unsafe_fallback(
    dummy_session: Path,
):
    mock_client = AsyncMock()
    mock_client.is_user_authorized.return_value = True
    request_names: list[str] = []

    class DummyUser:
        id = 1001
        first_name = "John"
        last_name = ""
        phone = ""

    class DummyContact:
        user_id = 1001

    class DummyContactsRes:
        def __init__(self) -> None:
            self.users = [DummyUser()]
            self.contacts = [DummyContact()]

    def handle_request(request):
        request_name = type(request).__name__
        request_names.append(request_name)
        if request_name == "GetContactsRequest":
            return DummyContactsRes()
        raise RuntimeError("selective delete failed")

    mock_client.side_effect = handle_request

    with patch("telethon.TelegramClient", return_value=mock_client):
        res = await delete_session_contacts(
            dummy_session, [(123, "hash")], target_user_ids=[1001]
        )

    assert res is False
    assert request_names == ["GetContactsRequest", "DeleteContactsRequest"]


@pytest.mark.asyncio
async def test_fetch_input_contacts_unions_zip_sessions(
    dummy_session: Path, tmp_path: Path
):
    second = _create_session(tmp_path / "second.session")
    zip_path = tmp_path / "sessions.zip"
    with zipfile.ZipFile(zip_path, "w") as zf:
        zf.write(dummy_session, arcname="1.session")
        zf.write(second, arcname="2.session")

    def make_client(user_id: int, name: str) -> AsyncMock:
        client = AsyncMock()
        client.is_user_authorized.return_value = True

        class DummyUser:
            def __init__(self) -> None:
                self.id = user_id
                self.first_name = name
                self.last_name = ""
                self.phone = ""

        class DummyContact:
            def __init__(self) -> None:
                self.user_id = user_id

        class DummyContactsRes:
            def __init__(self) -> None:
                self.users = [DummyUser()]
                self.contacts = [DummyContact()]

        client.side_effect = lambda _request: DummyContactsRes()
        return client

    clients = [make_client(1001, "Alice"), make_client(2002, "Bob")]
    with patch("telethon.TelegramClient", side_effect=clients):
        contacts = await fetch_input_contacts(zip_path, [(123, "hash")])

    assert [(item.user_id, item.first_name) for item in contacts] == [
        (1001, "Alice"),
        (2002, "Bob"),
    ]


@pytest.mark.asyncio
async def test_process_delete_contacts_single(dummy_session: Path, tmp_path: Path):
    mock_client = AsyncMock()
    mock_client.is_user_authorized.return_value = True

    with patch("telethon.TelegramClient", return_value=mock_client):
        res = await process_delete_contacts(
            dummy_session,
            tmp_path / "out",
            credentials=[(123, "hash")],
            target_user_ids=[1001],
        )

    assert res.total == 1
    assert res.deleted == 1
    assert res.failed == 0
    assert res.is_zip is False
    assert res.output_path is not None
    assert re.match(r"^Delete_Contacts_1_[a-f0-9]{6}\.session$", res.output_path.name)


@pytest.mark.asyncio
async def test_process_delete_contacts_zip(dummy_session: Path, tmp_path: Path):
    second = _create_session(tmp_path / "second.session")
    zip_path = tmp_path / "sessions.zip"
    with zipfile.ZipFile(zip_path, "w") as zf:
        zf.write(dummy_session, arcname="1.session")
        zf.write(second, arcname="2.session")

    def make_client(user_id: int) -> AsyncMock:
        client = AsyncMock()
        client.is_user_authorized.return_value = True

        class DummyUser:
            def __init__(self) -> None:
                self.id = user_id
                self.first_name = ""
                self.last_name = ""
                self.phone = ""

        class DummyContact:
            def __init__(self) -> None:
                self.user_id = user_id

        class DummyContactsRes:
            def __init__(self) -> None:
                self.users = [DummyUser()]
                self.contacts = [DummyContact()]

        def handle_request(request):
            if type(request).__name__ == "GetContactsRequest":
                return DummyContactsRes()
            return True

        client.side_effect = handle_request
        return client

    first_client = make_client(1001)
    second_client = make_client(2002)

    with patch("telethon.TelegramClient", side_effect=[first_client, second_client]):
        res = await process_delete_contacts(
            zip_path,
            tmp_path / "out",
            credentials=[(123, "hash")],
            target_user_ids=[1001],
        )

    assert res.total == 2
    assert res.deleted == 2
    assert res.failed == 0
    assert res.is_zip is True
    assert res.output_path is not None
    assert re.match(r"^Delete_Contacts_2_[a-f0-9]{6}\.zip$", res.output_path.name)
    assert first_client.await_count == 2
    assert second_client.await_count == 1


@pytest.mark.asyncio
async def test_delete_contact_noop_callback():
    callback_mock = AsyncMock(spec=CallbackQuery)
    callback_mock.answer = AsyncMock()
    await delete_contact_noop(callback_mock)
    callback_mock.answer.assert_called_once()


def test_delete_contact_locales_and_keyboards():
    assert len(ENTER_DELETE_CONTACT_PROMPT) == 6
    assert len(DELETE_CONTACT_SELECT_PROMPT) == 6
    assert len(DELETE_CONTACT_MESSAGES) == 6

    contacts = [
        ContactItem(
            user_id=100 + i, first_name=f"User{i}", last_name="", phone=f"111{i}"
        ).to_dict()
        for i in range(12)
    ]
    selected = {100, 101, 102}

    # Page 0 (5 per page)
    kb0 = delete_contact_selection_menu(
        contacts, selected, page=0, page_size=5, language="en"
    )
    assert kb0 is not None
    # 5 contact rows + 1 nav row + 1 action row + 1 confirm row + 1 cancel row = 9 rows
    assert len(kb0.inline_keyboard) == 9

    # Page 1
    kb1 = delete_contact_selection_menu(
        contacts, selected, page=1, page_size=5, language="en"
    )
    assert kb1 is not None
    assert len(kb1.inline_keyboard) == 9
    assert kb1.inline_keyboard[-1][0].callback_data == "action:cancel"

    res_kb = delete_contact_result_menu(12, 3, 0, "en")
    assert res_kb is not None
    assert len(res_kb.inline_keyboard) == 3
