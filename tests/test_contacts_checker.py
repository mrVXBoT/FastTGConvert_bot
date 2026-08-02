import sqlite3
import tempfile
import zipfile
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.keyboards import contacts_result_menu
from app.locales import CHECK_CONTACTS_MESSAGES, CHECK_CONTACTS_PROMPTS
from app.services.contacts_checker import (
    check_session_contacts_live,
    check_session_contacts_offline,
    process_contacts_check,
)
from app.services.files import UnsafeArchiveError


@pytest.mark.asyncio
async def test_process_contacts_check_single_session() -> None:
    with tempfile.TemporaryDirectory() as tmp:
        tmp_path = Path(tmp)
        sess_file = tmp_path / "test.session"

        with sqlite3.connect(sess_file) as conn:
            conn.execute("CREATE TABLE sessions (auth_key BLOB)")
            conn.execute(
                "INSERT INTO sessions VALUES (?)", (b"valid_key_1234567890_123456",)
            )
            conn.execute("CREATE TABLE contacts (id INTEGER PRIMARY KEY, phone TEXT)")
            conn.execute("INSERT INTO contacts VALUES (1, '+123456789')")

        res = await process_contacts_check(sess_file, tmp_path / "outbox")
        assert res.checked == 1
        assert res.ok == 1
        assert res.error == 0
        assert res.ok_zip_path is not None
        assert res.ok_zip_path.name.startswith("contacts_ok_")
        assert res.ok_zip_path.exists()

        with zipfile.ZipFile(res.ok_zip_path) as zf:
            names = zf.namelist()
            assert "test.session" in names


@pytest.mark.asyncio
async def test_process_contacts_check_invalid_session() -> None:
    with tempfile.TemporaryDirectory() as tmp:
        tmp_path = Path(tmp)
        sess_file = tmp_path / "invalid.session"
        sess_file.write_bytes(b"not a sqlite db")

        res = await process_contacts_check(sess_file, tmp_path / "outbox")
        assert res.checked == 1
        assert res.ok == 0
        assert res.error == 1
        assert res.ok_zip_path is None


def test_check_session_contacts_offline_telethon_standard_session_without_contacts_table() -> (
    None
):
    with tempfile.TemporaryDirectory() as tmp:
        sess_file = Path(tmp) / "std_telethon.session"
        with sqlite3.connect(sess_file) as conn:
            conn.execute("CREATE TABLE sessions (auth_key BLOB)")
            conn.execute(
                "INSERT INTO sessions VALUES (?)", (b"valid_key_1234567890_123456",)
            )
            # Standard Telethon session with valid auth key but missing contacts table is valid

        is_ok, count = check_session_contacts_offline(sess_file)
        assert is_ok is True
        assert count == 0


def test_check_session_contacts_offline_missing_auth_key_rejected() -> None:
    with tempfile.TemporaryDirectory() as tmp:
        sess_file = Path(tmp) / "no_auth.session"
        with sqlite3.connect(sess_file) as conn:
            conn.execute("CREATE TABLE sessions (auth_key BLOB)")
            conn.execute("INSERT INTO sessions VALUES (?)", (b"",))

        is_ok, count = check_session_contacts_offline(sess_file)
        assert is_ok is False
        assert count == 0


@pytest.mark.asyncio
async def test_live_check_unauthorized_returns_false_without_offline_fallback() -> None:
    with tempfile.TemporaryDirectory() as tmp:
        sess_file = Path(tmp) / "unauth.session"
        with sqlite3.connect(sess_file) as conn:
            conn.execute("CREATE TABLE sessions (auth_key BLOB)")
            conn.execute(
                "INSERT INTO sessions VALUES (?)", (b"valid_key_1234567890_123456",)
            )
            conn.execute("CREATE TABLE contacts (id INTEGER PRIMARY KEY, phone TEXT)")

        mock_client = AsyncMock()
        mock_client.connect = AsyncMock()
        mock_client.is_user_authorized = AsyncMock(return_value=False)
        mock_client.disconnect = AsyncMock()

        with patch("telethon.TelegramClient", return_value=mock_client):
            is_ok, count = await check_session_contacts_live(
                sess_file, [(12345, "hash")]
            )
            assert is_ok is False
            assert count == 0

            res = await process_contacts_check(
                sess_file, Path(tmp) / "outbox", credentials=[(12345, "hash")]
            )
            assert res.checked == 1
            assert res.ok == 0
            assert res.error == 1


@pytest.mark.asyncio
async def test_transient_network_error_tries_next_credential_and_succeeds() -> None:
    with tempfile.TemporaryDirectory() as tmp:
        sess_file = Path(tmp) / "test.session"
        sess_file.write_bytes(b"dummy")

        mock_client_fail = AsyncMock()
        mock_client_fail.connect = AsyncMock(side_effect=OSError("Network down"))
        mock_client_fail.disconnect = AsyncMock()

        mock_client_ok = AsyncMock()
        mock_client_ok.connect = AsyncMock()
        mock_client_ok.is_user_authorized = AsyncMock(return_value=True)
        mock_res = type("ContactsRes", (), {"contacts": [1, 2, 3]})()
        mock_client_ok.side_effect = None
        mock_client_ok.return_value = mock_res
        mock_client_ok.disconnect = AsyncMock()

        with patch(
            "telethon.TelegramClient", side_effect=[mock_client_fail, mock_client_ok]
        ):
            is_ok, count = await check_session_contacts_live(
                sess_file, [(111, "h1"), (222, "h2")]
            )
            assert is_ok is True
            assert count == 3


@pytest.mark.asyncio
async def test_process_contacts_check_zip_slip_rejected() -> None:
    with tempfile.TemporaryDirectory() as tmp:
        tmp_path = Path(tmp)
        zip_file = tmp_path / "malicious.zip"
        with zipfile.ZipFile(zip_file, "w") as z:
            z.writestr("../session.session", b"dummy")

        with pytest.raises(UnsafeArchiveError) as exc_info:
            await process_contacts_check(zip_file, tmp_path / "outbox")
        assert exc_info.value.code in ("zip_unsafe_path", "zip_slip")


@pytest.mark.asyncio
async def test_process_contacts_check_too_many_members_rejected() -> None:
    with tempfile.TemporaryDirectory() as tmp:
        tmp_path = Path(tmp)
        zip_file = tmp_path / "too_many.zip"
        with patch("app.services.contacts_checker.MAX_ZIP_MEMBERS", 2):
            with zipfile.ZipFile(zip_file, "w") as z:
                z.writestr("1.session", b"a")
                z.writestr("2.session", b"b")
                z.writestr("3.session", b"c")

            with pytest.raises(UnsafeArchiveError) as exc_info:
                await process_contacts_check(zip_file, tmp_path / "outbox")
            assert exc_info.value.code in ("zip_too_many_members", "too_many_members")


@pytest.mark.asyncio
async def test_process_contacts_check_zip_bomb_rejected() -> None:
    with tempfile.TemporaryDirectory() as tmp:
        tmp_path = Path(tmp)
        zip_file = tmp_path / "zip_bomb.zip"
        with patch("app.services.contacts_checker.MAX_ZIP_UNCOMPRESSED_BYTES", 10):
            with zipfile.ZipFile(zip_file, "w") as z:
                z.writestr("large.session", b"0" * 100)

            with pytest.raises(UnsafeArchiveError) as exc_info:
                await process_contacts_check(zip_file, tmp_path / "outbox")
            assert exc_info.value.code in ("zip_uncompressed_limit", "zip_bomb")


@pytest.mark.asyncio
async def test_process_contacts_check_temp_dir_cleaned_on_exception() -> None:
    mock_tmp_instance = MagicMock()
    mock_tmp_instance.name = tempfile.mkdtemp()
    mock_tmp_instance.cleanup = MagicMock()

    with tempfile.TemporaryDirectory() as real_tmp:
        tmp_path = Path(real_tmp)
        zip_file = tmp_path / "invalid.zip"
        with zipfile.ZipFile(zip_file, "w") as z:
            z.writestr("../bad.session", b"dummy")

        with (
            patch("tempfile.TemporaryDirectory", return_value=mock_tmp_instance),
            pytest.raises(UnsafeArchiveError),
        ):
            await process_contacts_check(zip_file, tmp_path / "outbox")

        assert mock_tmp_instance.cleanup.called is True


@pytest.mark.asyncio
async def test_process_contacts_check_unique_output_path() -> None:
    with tempfile.TemporaryDirectory() as tmp:
        tmp_path = Path(tmp)
        sess_file = tmp_path / "test.session"
        with sqlite3.connect(sess_file) as conn:
            conn.execute("CREATE TABLE sessions (auth_key BLOB)")
            conn.execute(
                "INSERT INTO sessions VALUES (?)", (b"valid_key_1234567890_123456",)
            )
            conn.execute("CREATE TABLE contacts (id INTEGER PRIMARY KEY)")

        res1 = await process_contacts_check(sess_file, tmp_path / "outbox")
        res2 = await process_contacts_check(sess_file, tmp_path / "outbox")

        assert res1.ok_zip_path is not None and res2.ok_zip_path is not None
        assert res1.ok_zip_path != res2.ok_zip_path
        assert res1.ok_zip_path.name != res2.ok_zip_path.name


def test_contacts_localization_all_languages() -> None:
    for lang in ("bn", "en", "hi", "ur", "ar", "zh"):
        assert lang in CHECK_CONTACTS_PROMPTS
        assert lang in CHECK_CONTACTS_MESSAGES
        msgs = CHECK_CONTACTS_MESSAGES[lang]
        rendered = msgs["done"].format(checked=5, ok=3, error=2)
        assert "5" in rendered and "3" in rendered and "2" in rendered

        menu = contacts_result_menu(5, 3, 2, lang)
        assert len(menu.inline_keyboard) == 3
        assert menu.inline_keyboard[0][0].text == msgs["checked"]
        assert menu.inline_keyboard[0][1].text == "5"
        assert menu.inline_keyboard[1][0].text == msgs["ok"]
        assert menu.inline_keyboard[1][1].text == "3"
        assert menu.inline_keyboard[2][0].text == msgs["error"]
        assert menu.inline_keyboard[2][1].text == "2"
