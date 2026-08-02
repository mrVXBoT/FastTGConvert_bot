import sqlite3
import zipfile
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from aiogram.fsm.context import FSMContext
from aiogram.types import Message
from telethon.tl.types.account import (  # type: ignore[import-untyped]
    ResetPasswordOk,
    ResetPasswordRequestedWait,
)

from app.handlers.files import (
    _edit_two_factor_flow,
    _two_factor_failure_details,
    receive_change_2fa_new_password,
    receive_change_2fa_old_password,
)
from app.keyboards import two_factor_result_menu
from app.locales import (
    CHANGE_2FA_PROMPTS,
    DISABLE_2FA_PROMPTS,
    ENTER_CURRENT_2FA_PROMPT,
    ENTER_NEW_2FA_PROMPT,
    LANGUAGES,
    RESET_2FA_PROMPTS,
    TWO_FACTOR_ERRORS,
    TWO_FACTOR_MESSAGES,
)
from app.services.two_factor import (
    TwoFactorResult,
    _reset_error_reason,
    process_change_2fa,
    process_disable_2fa,
    process_reset_2fa,
)


def _create_session(path: Path) -> Path:
    with sqlite3.connect(path) as conn:
        conn.execute("CREATE TABLE version (version integer primary key)")
        conn.execute("INSERT INTO version VALUES (7)")
        conn.execute(
            "CREATE TABLE sessions (dc_id integer primary key, server_address"
            " text, port integer, auth_key blob, takeout_id integer)"
        )
        conn.execute(
            "INSERT INTO sessions VALUES (2, '149.154.167.50', 443, ?, 0)",
            (b"\x05" * 256,),
        )
        conn.execute(
            "CREATE TABLE entities (id integer primary key, hash integer,"
            " username text, phone text, name text, date integer)"
        )
        conn.execute(
            "INSERT INTO entities VALUES (8886120375, 1, 'testuser', '573118508561', 'Test', 1600000000)"
        )
    return path


@pytest.fixture
def dummy_session(tmp_path: Path) -> Path:
    return _create_session(tmp_path / "test.session")


def test_2fa_locales_and_keyboards():
    for lang in LANGUAGES:
        assert lang in CHANGE_2FA_PROMPTS
        assert lang in DISABLE_2FA_PROMPTS
        assert lang in RESET_2FA_PROMPTS
        assert lang in ENTER_CURRENT_2FA_PROMPT
        assert lang in ENTER_NEW_2FA_PROMPT
        assert lang in TWO_FACTOR_MESSAGES
        assert lang in TWO_FACTOR_ERRORS
        assert "/cancel" not in CHANGE_2FA_PROMPTS[lang]
        assert "/cancel" not in DISABLE_2FA_PROMPTS[lang]
        assert "/cancel" not in RESET_2FA_PROMPTS[lang]
        assert "/cancel" not in ENTER_CURRENT_2FA_PROMPT[lang]
        assert "/cancel" not in ENTER_NEW_2FA_PROMPT[lang]
        assert "{pending}" in TWO_FACTOR_MESSAGES[lang]["done_reset"]
        assert TWO_FACTOR_MESSAGES[lang]["btn_pending"]
        assert TWO_FACTOR_ERRORS[lang]["fresh_authorization_forbidden"]

        kb = two_factor_result_menu(1, 1, 0, lang)
        assert len(kb.inline_keyboard) == 3
        pending_kb = two_factor_result_menu(1, 0, 0, lang, pending=1)
        assert len(pending_kb.inline_keyboard) == 4


def test_reset_failure_reason_is_localized_for_the_user() -> None:
    class FreshResetAuthorisationForbiddenError(Exception):
        pass

    reason = _reset_error_reason(FreshResetAuthorisationForbiddenError())
    result = TwoFactorResult(
        total=1,
        success=0,
        failed=1,
        failure_reasons=(reason,),
    )

    details = _two_factor_failure_details(result, "en")

    assert "newly authorized session" in details
    assert "FreshResetAuthorisationForbiddenError" not in details


@pytest.mark.asyncio
async def test_process_change_2fa(dummy_session: Path, tmp_path: Path):
    mock_client = AsyncMock()
    mock_client.is_user_authorized.return_value = True
    mock_client.edit_2fa.return_value = True

    with patch("telethon.TelegramClient", return_value=mock_client):
        res = await process_change_2fa(
            dummy_session,
            tmp_path / "out",
            "old_pass",
            "new_pass",
            [(123, "hash")],
        )

    assert res.total == 1
    assert res.success == 1
    assert res.failed == 0
    assert res.output_path is not None
    assert res.output_path.exists()
    assert "2FA_Changed_Success" in res.output_path.name
    mock_client.edit_2fa.assert_called_once_with(
        current_password="old_pass", new_password="new_pass"
    )


@pytest.mark.asyncio
async def test_process_disable_2fa(dummy_session: Path, tmp_path: Path):
    mock_client = AsyncMock()
    mock_client.is_user_authorized.return_value = True
    mock_client.edit_2fa.return_value = True

    with patch("telethon.TelegramClient", return_value=mock_client):
        res = await process_disable_2fa(
            dummy_session,
            tmp_path / "out",
            "current_pass",
            [(123, "hash")],
        )

    assert res.total == 1
    assert res.success == 1
    assert res.failed == 0
    assert res.output_path is not None
    assert res.output_path.exists()
    assert "2FA_Disabled_Success" in res.output_path.name
    mock_client.edit_2fa.assert_called_once_with(
        current_password="current_pass", new_password=None
    )


@pytest.mark.asyncio
async def test_process_reset_2fa(dummy_session: Path, tmp_path: Path):
    mock_client = AsyncMock()
    mock_client.is_user_authorized.return_value = True
    mock_client.return_value = ResetPasswordOk()

    with patch("telethon.TelegramClient", return_value=mock_client):
        res = await process_reset_2fa(
            dummy_session,
            tmp_path / "out",
            [(123, "hash")],
        )

    assert res.total == 1
    assert res.success == 1
    assert res.failed == 0
    assert res.output_path is not None
    assert res.output_path.exists()
    assert "2FA_Reset" in res.output_path.name


@pytest.mark.asyncio
async def test_false_edit_2fa_result_is_not_counted_as_success(
    dummy_session: Path, tmp_path: Path
) -> None:
    mock_client = AsyncMock()
    mock_client.is_user_authorized.return_value = True
    mock_client.edit_2fa.return_value = False

    with patch("telethon.TelegramClient", return_value=mock_client):
        result = await process_change_2fa(
            dummy_session,
            tmp_path / "out",
            "old_pass",
            "new_pass",
            [(123, "hash")],
        )

    assert result.success == 0
    assert result.failed == 1
    assert result.output_path is None


@pytest.mark.asyncio
async def test_reset_wait_response_is_pending_not_success(
    dummy_session: Path, tmp_path: Path
) -> None:
    mock_client = AsyncMock()
    mock_client.is_user_authorized.return_value = True
    mock_client.return_value = ResetPasswordRequestedWait(until_date=None)

    with patch("telethon.TelegramClient", return_value=mock_client):
        result = await process_reset_2fa(
            dummy_session,
            tmp_path / "out",
            [(123, "hash")],
        )

    assert result.total == 1
    assert result.success == 0
    assert result.pending == 1
    assert result.failed == 0
    assert result.output_path is None


@pytest.mark.asyncio
async def test_process_change_2fa_zip(dummy_session: Path, tmp_path: Path):
    second = _create_session(tmp_path / "second.session")
    zip_path = tmp_path / "sessions.zip"
    with zipfile.ZipFile(zip_path, "w") as zf:
        zf.write(dummy_session, arcname="1.session")
        zf.write(second, arcname="2.session")

    mock_client = AsyncMock()
    mock_client.is_user_authorized.return_value = True
    mock_client.edit_2fa.return_value = True

    with patch("telethon.TelegramClient", return_value=mock_client):
        res = await process_change_2fa(
            zip_path,
            tmp_path / "out",
            "old_pass",
            "new_pass",
            [(123, "hash")],
        )

    assert res.total == 2
    assert res.success == 2
    assert res.is_zip is True
    assert res.output_path is not None
    assert res.output_path.name.endswith(".zip")


@pytest.mark.asyncio
async def test_single_session_zip_stays_a_zip(
    dummy_session: Path, tmp_path: Path
) -> None:
    zip_path = tmp_path / "single.zip"
    with zipfile.ZipFile(zip_path, "w") as archive:
        archive.write(dummy_session, arcname="1.session")
    mock_client = AsyncMock()
    mock_client.is_user_authorized.return_value = True
    mock_client.edit_2fa.return_value = True

    with patch("telethon.TelegramClient", return_value=mock_client):
        result = await process_change_2fa(
            zip_path,
            tmp_path / "out",
            "old_pass",
            "new_pass",
            [(123, "hash")],
        )

    assert result.success == 1
    assert result.is_zip is True
    assert result.output_path is not None
    assert result.output_path.suffix == ".zip"


@pytest.mark.asyncio
async def test_old_password_message_is_deleted_and_stored_exactly() -> None:
    message = MagicMock(spec=Message)
    message.from_user = MagicMock(id=123)
    message.text = "  exact password  "
    message.delete = AsyncMock()
    message.answer = AsyncMock()
    state = AsyncMock(spec=FSMContext)
    state.get_data.return_value = {}

    with patch("app.handlers.files.user_language", return_value="en"):
        await receive_change_2fa_old_password(message, MagicMock(), state, MagicMock())

    message.delete.assert_awaited_once()
    state.update_data.assert_awaited_once_with(old_password="  exact password  ")


@pytest.mark.asyncio
async def test_new_password_is_deleted_and_old_password_removed_from_state(
    tmp_path: Path,
) -> None:
    upload = tmp_path / "input.session"
    upload.write_bytes(b"session")
    message = MagicMock(spec=Message)
    message.from_user = MagicMock(id=123)
    message.text = "new exact password"
    message.delete = AsyncMock()
    status = MagicMock(spec=Message)
    status.edit_text = AsyncMock()
    message.answer = AsyncMock(return_value=status)
    message.answer_document = AsyncMock()
    state = AsyncMock(spec=FSMContext)
    state.get_data.return_value = {
        "two_factor_session_files": [str(upload)],
        "two_factor_index": 0,
        "old_password": "old exact password",
    }
    settings = MagicMock()
    settings.storage_dir = tmp_path
    settings.api_credential_list = [(123, "hash")]

    with (
        patch("app.handlers.files.user_language", return_value="en"),
        patch(
            "app.handlers.files.edit_two_factor_session",
            new_callable=AsyncMock,
            return_value=True,
        ) as edit_session,
        patch(
            "app.handlers.files._advance_two_factor_batch",
            new_callable=AsyncMock,
        ) as advance_batch,
    ):
        await receive_change_2fa_new_password(
            message, MagicMock(), state, settings, MagicMock()
        )

    message.delete.assert_awaited_once()
    state.update_data.assert_awaited_once_with(old_password=None)
    edit_session.assert_awaited_once_with(
        upload,
        settings.api_credential_list,
        current_password="old exact password",
        new_password="new exact password",
    )
    advance_batch.assert_awaited_once()


@pytest.mark.asyncio
async def test_two_factor_flow_edits_existing_message_instead_of_answering() -> None:
    message = MagicMock(spec=Message)
    message.chat = MagicMock(id=456)
    message.answer = AsyncMock()
    edited = MagicMock(spec=Message)
    bot = MagicMock()
    bot.edit_message_text = AsyncMock(return_value=edited)
    state = AsyncMock(spec=FSMContext)
    state.get_data.return_value = {"flow_message_id": 789}
    markup = two_factor_result_menu(1, 1, 0, "en")

    result = await _edit_two_factor_flow(message, bot, state, "updated", markup)

    assert result is edited
    bot.edit_message_text.assert_awaited_once_with(
        chat_id=456,
        message_id=789,
        text="updated",
        reply_markup=markup,
    )
    message.answer.assert_not_awaited()
