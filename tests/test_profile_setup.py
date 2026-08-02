import re
import sqlite3
import zipfile
from pathlib import Path
from unittest.mock import AsyncMock, patch

import pytest
from aiogram.types import CallbackQuery

from app.handlers.files import profile_setup_noop
from app.keyboards import (
    profile_setup_account_menu,
    profile_setup_result_menu,
)
from app.locales import (
    ENTER_PROFILE_SETUP_PROMPT,
    PROFILE_SETUP_ACCOUNT_PROMPT,
    PROFILE_SETUP_MESSAGES,
)
from app.services.profile_setup import (
    fetch_account_profile,
    package_profile_setup_results,
    update_account_profile,
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
async def test_fetch_account_profile(dummy_session: Path):
    mock_client = AsyncMock()
    mock_client.is_user_authorized.return_value = True

    class DummyMe:
        id = 12345
        phone = "989123456789"
        first_name = "Alice"
        last_name = "Smith"
        username = "alicesmith"

    class DummyFullUser:
        about = "Bio text"

    class DummyFullRes:
        full_user = DummyFullUser()

    mock_client.get_me.return_value = DummyMe()
    mock_client.side_effect = lambda req: DummyFullRes()

    with patch("telethon.TelegramClient", return_value=mock_client):
        info = await fetch_account_profile(dummy_session, [(123, "hash")])

    assert info is not None
    assert info.user_id == 12345
    assert info.phone == "989123456789"
    assert info.first_name == "Alice"
    assert info.last_name == "Smith"
    assert info.username == "alicesmith"
    assert info.about == "Bio text"


@pytest.mark.asyncio
async def test_update_account_profile(dummy_session: Path, tmp_path: Path):
    mock_client = AsyncMock()
    mock_client.is_user_authorized.return_value = True

    class DummyMe:
        first_name = "Alice"
        last_name = "Smith"

    mock_client.get_me.return_value = DummyMe()
    mock_client.upload_file.return_value = "file_handle"

    photo_file = tmp_path / "avatar.jpg"
    photo_file.write_bytes(b"\xff\xd8\xff\xe0")

    with patch("telethon.TelegramClient", return_value=mock_client):
        ok = await update_account_profile(
            dummy_session,
            [(123, "hash")],
            first_name="Bob",
            last_name="Jones",
            username="bobjones",
            about="New bio",
            photo_path=photo_file,
        )

    assert ok is True
    assert mock_client.upload_file.called


@pytest.mark.asyncio
async def test_package_profile_setup_results_single(
    dummy_session: Path, tmp_path: Path
):
    res = package_profile_setup_results(
        [dummy_session],
        tmp_path / "out",
        modified_count=1,
        skipped_count=0,
        failed_count=0,
    )

    assert res.total == 1
    assert res.modified == 1
    assert res.skipped == 0
    assert res.failed == 0
    assert res.is_zip is False
    assert res.output_path is not None
    assert re.match(r"^Profile_Setup_1_[a-f0-9]{6}\.session$", res.output_path.name)


@pytest.mark.asyncio
async def test_package_profile_setup_results_zip(dummy_session: Path, tmp_path: Path):
    second = _create_session(tmp_path / "second.session")
    res = package_profile_setup_results(
        [dummy_session, second],
        tmp_path / "out",
        modified_count=1,
        skipped_count=1,
        failed_count=0,
    )

    assert res.total == 2
    assert res.modified == 1
    assert res.skipped == 1
    assert res.failed == 0
    assert res.is_zip is True
    assert res.output_path is not None
    assert re.match(r"^Profile_Setup_2_[a-f0-9]{6}\.zip$", res.output_path.name)

    with zipfile.ZipFile(res.output_path, "r") as zf:
        assert len(zf.namelist()) == 2


@pytest.mark.asyncio
async def test_profile_setup_noop_callback():
    callback_mock = AsyncMock(spec=CallbackQuery)
    callback_mock.answer = AsyncMock()
    await profile_setup_noop(callback_mock)
    callback_mock.answer.assert_called_once()


def test_profile_setup_locales_and_keyboards():
    assert len(ENTER_PROFILE_SETUP_PROMPT) == 6
    assert len(PROFILE_SETUP_ACCOUNT_PROMPT) == 6
    assert len(PROFILE_SETUP_MESSAGES) == 6

    kb_acc = profile_setup_account_menu("en")
    assert kb_acc is not None
    assert len(kb_acc.inline_keyboard) == 5

    kb_res = profile_setup_result_menu(5, 3, 1, 1, "en")
    assert kb_res is not None
    assert len(kb_res.inline_keyboard) == 4
