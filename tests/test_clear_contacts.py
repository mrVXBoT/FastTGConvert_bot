import re
import sqlite3
import zipfile
from pathlib import Path
from unittest.mock import AsyncMock, patch

import pytest
from aiogram.types import CallbackQuery

from app.handlers.files import clear_contacts_noop
from app.keyboards import clear_contacts_result_menu
from app.locales import CLEAR_CONTACTS_MESSAGES, ENTER_CLEAR_CONTACTS_PROMPT
from app.services.clear_contacts import (
    clear_session_contacts,
    process_clear_contacts,
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
async def test_clear_session_contacts_success(dummy_session: Path):
    mock_client = AsyncMock()
    mock_client.is_user_authorized.return_value = True
    request_names: list[str] = []

    class DummyContact:
        user_id = 987654321

    class DummyUser:
        id = 987654321

    class DummyContactsRes:
        def __init__(self) -> None:
            self.contacts = [DummyContact()]
            self.users = [DummyUser()]

    def handle_request(req):
        request_names.append(type(req).__name__)
        if "GetContactsRequest" in type(req).__name__:
            return DummyContactsRes()
        return True

    mock_client.side_effect = handle_request

    with patch("telethon.TelegramClient", return_value=mock_client):
        res = await clear_session_contacts(dummy_session, [(123, "hash")])

    assert res is True
    assert request_names == [
        "GetContactsRequest",
        "DeleteContactsRequest",
        "ResetSavedRequest",
    ]


@pytest.mark.asyncio
async def test_clear_session_contacts_delete_failure_is_failed(dummy_session: Path):
    mock_client = AsyncMock()
    mock_client.is_user_authorized.return_value = True
    request_names: list[str] = []

    class DummyContact:
        user_id = 987654321

    class DummyContactsRes:
        def __init__(self) -> None:
            self.contacts = [DummyContact()]
            self.users: list[object] = []

    def handle_request(req):
        request_name = type(req).__name__
        request_names.append(request_name)
        if request_name == "GetContactsRequest":
            return DummyContactsRes()
        if request_name == "DeleteContactsRequest":
            raise RuntimeError("delete failed")
        return True

    mock_client.side_effect = handle_request

    with patch("telethon.TelegramClient", return_value=mock_client):
        res = await clear_session_contacts(dummy_session, [(123, "hash")])

    assert res is False
    assert request_names == ["GetContactsRequest", "DeleteContactsRequest"]


@pytest.mark.asyncio
async def test_clear_session_contacts_reset_saved_failure_is_failed(
    dummy_session: Path,
):
    mock_client = AsyncMock()
    mock_client.is_user_authorized.return_value = True

    class DummyContactsRes:
        def __init__(self) -> None:
            self.contacts: list[object] = []
            self.users: list[object] = []

    def handle_request(req):
        if type(req).__name__ == "GetContactsRequest":
            return DummyContactsRes()
        raise RuntimeError("reset saved failed")

    mock_client.side_effect = handle_request

    with patch("telethon.TelegramClient", return_value=mock_client):
        res = await clear_session_contacts(dummy_session, [(123, "hash")])

    assert res is False


@pytest.mark.asyncio
async def test_clear_session_contacts_unauthorized(dummy_session: Path):
    mock_client = AsyncMock()
    mock_client.is_user_authorized.return_value = False

    with patch("telethon.TelegramClient", return_value=mock_client):
        res = await clear_session_contacts(dummy_session, [(123, "hash")])

    assert res is False


@pytest.mark.asyncio
async def test_process_clear_contacts_single(dummy_session: Path, tmp_path: Path):
    mock_client = AsyncMock()
    mock_client.is_user_authorized.return_value = True

    class DummyContactsRes:
        def __init__(self) -> None:
            self.contacts: list[object] = []

    mock_client.side_effect = lambda req: (
        DummyContactsRes() if "GetContactsRequest" in type(req).__name__ else None
    )

    with patch("telethon.TelegramClient", return_value=mock_client):
        res = await process_clear_contacts(
            dummy_session,
            tmp_path / "out",
            [(123, "hash")],
        )

    assert res.total == 1
    assert res.cleared == 1
    assert res.failed == 0
    assert res.is_zip is False
    assert res.output_path is not None
    assert re.match(r"^Contacts_Cleared_1_[a-f0-9]{6}\.session$", res.output_path.name)


@pytest.mark.asyncio
async def test_process_clear_contacts_zip(dummy_session: Path, tmp_path: Path):
    second = _create_session(tmp_path / "second.session")
    zip_path = tmp_path / "sessions.zip"
    with zipfile.ZipFile(zip_path, "w") as zf:
        zf.write(dummy_session, arcname="1.session")
        zf.write(second, arcname="2.session")

    mock_client = AsyncMock()
    mock_client.is_user_authorized.return_value = True

    class DummyContactsRes:
        def __init__(self) -> None:
            self.contacts: list[object] = []

    mock_client.side_effect = lambda req: (
        DummyContactsRes() if "GetContactsRequest" in type(req).__name__ else None
    )

    with patch("telethon.TelegramClient", return_value=mock_client):
        res = await process_clear_contacts(
            zip_path,
            tmp_path / "out",
            [(123, "hash")],
        )

    assert res.total == 2
    assert res.cleared == 2
    assert res.failed == 0
    assert res.is_zip is True
    assert res.output_path is not None
    assert re.match(r"^Contacts_Cleared_2_[a-f0-9]{6}\.zip$", res.output_path.name)


@pytest.mark.asyncio
async def test_clear_contacts_noop_callback():
    callback_mock = AsyncMock(spec=CallbackQuery)
    callback_mock.answer = AsyncMock()
    await clear_contacts_noop(callback_mock)
    callback_mock.answer.assert_called_once()


def test_clear_contacts_locales_and_keyboards():
    assert len(ENTER_CLEAR_CONTACTS_PROMPT) == 6
    assert len(CLEAR_CONTACTS_MESSAGES) == 6

    kb = clear_contacts_result_menu(10, 8, 2, "en")
    assert kb is not None
    assert len(kb.inline_keyboard) == 4
