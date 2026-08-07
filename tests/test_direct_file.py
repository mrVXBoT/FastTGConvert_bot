from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery, Message

from app.handlers.files import (
    _expire_direct_file,
    process_direct_document_upload,
    process_quick_action,
)
from app.services.account_to_txt import AccountTxtResult
from app.services.session_to_tdata import SessionToTdataResult
from app.services.two_factor import TwoFactorResult
from app.session_results import SessionCheckResult
from app.states import DirectFile, SplitFile


@pytest.mark.asyncio
async def test_direct_file_really_expires_and_is_deleted(tmp_path: Path) -> None:
    upload = tmp_path / "upload.session"
    upload.write_bytes(b"temporary")
    state = AsyncMock(spec=FSMContext)
    state.get_state.return_value = DirectFile.waiting_for_action.state
    state.get_data.return_value = {
        "direct_token": "token",
        "temp_file_path": str(upload),
    }
    prompt = AsyncMock(spec=Message)
    prompt.edit_text = AsyncMock()

    await _expire_direct_file(state, prompt, "token", "en", delay=0)

    assert not upload.exists()
    state.clear.assert_awaited_once()
    prompt.edit_text.assert_awaited_once()


@pytest.mark.asyncio
async def test_old_timer_does_not_delete_replacement_file(tmp_path: Path) -> None:
    upload = tmp_path / "replacement.session"
    upload.write_bytes(b"new")
    state = AsyncMock(spec=FSMContext)
    state.get_state.return_value = DirectFile.waiting_for_action.state
    state.get_data.return_value = {
        "direct_token": "new-token",
        "temp_file_path": str(upload),
    }
    prompt = AsyncMock(spec=Message)

    await _expire_direct_file(state, prompt, "old-token", "en", delay=0)

    assert upload.exists()
    state.clear.assert_not_awaited()


@pytest.mark.asyncio
async def test_sending_file_again_replaces_and_deletes_previous(
    tmp_path: Path,
) -> None:
    previous = tmp_path / "previous.session"
    previous.write_bytes(b"old")
    downloaded = tmp_path / "downloaded.session"
    downloaded.write_bytes(b"new")
    message = MagicMock(spec=Message)
    message.from_user = MagicMock(id=123)
    message.document = MagicMock()
    prompt = MagicMock(spec=Message)
    message.answer = AsyncMock(return_value=prompt)
    state = AsyncMock(spec=FSMContext)
    state.get_data.return_value = {"temp_file_path": str(previous)}

    def discard_task(coroutine: object) -> MagicMock:
        coroutine.close()  # type: ignore[attr-defined]
        return MagicMock()

    with (
        patch("app.handlers.files.user_language", return_value="en"),
        patch(
            "app.handlers.files.download_document",
            new_callable=AsyncMock,
            return_value=(downloaded, "573118508561.session"),
        ),
        patch("app.handlers.files.asyncio.create_task", side_effect=discard_task),
    ):
        await process_direct_document_upload(
            message, MagicMock(), state, MagicMock(), MagicMock()
        )

    assert not previous.exists()
    assert not downloaded.exists()
    state.clear.assert_awaited_once()
    stored = state.set_data.await_args.args[0]
    replacement = Path(stored["temp_file_path"])
    assert replacement.exists()
    assert replacement.name.startswith("573118508561-")
    assert replacement.suffix == ".session"


@pytest.mark.asyncio
async def test_quick_session_check_executes_and_cleans_input(tmp_path: Path) -> None:
    upload = tmp_path / "account.session"
    upload.write_bytes(b"session")
    callback = MagicMock(spec=CallbackQuery)
    callback.data = "quick:session_check"
    callback.from_user = MagicMock(id=123)
    callback.answer = AsyncMock()
    callback.message = MagicMock(spec=Message)
    callback.message.edit_text = AsyncMock(return_value=callback.message)

    state = AsyncMock(spec=FSMContext)
    state.get_data.return_value = {
        "temp_file_path": str(upload),
        "original_name": "account.session",
    }
    settings = MagicMock()
    settings.api_credential_list = [(1, "hash")]
    settings.spambot_timeout = 15
    result = SessionCheckResult(checked=1, active=1, frozen=0, invalid=0)

    with (
        patch("app.handlers.files.user_language", return_value="en"),
        patch(
            "app.handlers.files.check_sessions_detailed",
            new_callable=AsyncMock,
            return_value=(result, []),
        ) as checker,
    ):
        await process_quick_action(
            callback,
            MagicMock(),
            state,
            settings,
            MagicMock(),
        )

    checker.assert_awaited_once()
    assert callback.message.edit_text.await_count == 2
    assert not upload.exists()
    state.clear.assert_awaited_once()


@pytest.mark.asyncio
async def test_quick_file_split_reuses_received_file(tmp_path: Path) -> None:
    upload = tmp_path / "account.session"
    upload.write_bytes(b"session")
    callback = MagicMock(spec=CallbackQuery)
    callback.data = "quick:file_split"
    callback.from_user = MagicMock(id=123)
    callback.answer = AsyncMock()
    callback.message = MagicMock(spec=Message)
    callback.message.edit_text = AsyncMock(return_value=callback.message)
    state = AsyncMock(spec=FSMContext)
    state.get_data.return_value = {
        "temp_file_path": str(upload),
        "original_name": "account.session",
    }

    with (
        patch("app.handlers.files.user_language", return_value="en"),
        patch(
            "app.handlers.files.inspect_session_split",
            new_callable=AsyncMock,
            return_value=1,
        ),
    ):
        await process_quick_action(
            callback, MagicMock(), state, MagicMock(), MagicMock()
        )

    assert upload.exists()
    state.set_state.assert_awaited_with(SplitFile.waiting_for_split_type)
    stored = state.set_data.await_args.args[0]
    assert stored["source_path"] == str(upload)
    assert stored["session_count"] == 1


@pytest.mark.asyncio
async def test_quick_session_to_tdata_uses_real_locale_keys_and_cleans(
    tmp_path: Path,
) -> None:
    upload = tmp_path / "123456789.session"
    upload.write_bytes(b"session")
    output = tmp_path / "result.zip"
    output.write_bytes(b"zip")
    callback = MagicMock(spec=CallbackQuery)
    callback.data = "quick:session_to_tdata"
    callback.from_user = MagicMock(id=123)
    callback.answer = AsyncMock()
    callback.message = MagicMock(spec=Message)
    callback.message.edit_text = AsyncMock(return_value=callback.message)
    callback.message.answer_document = AsyncMock()
    state = AsyncMock(spec=FSMContext)
    state.get_data.return_value = {
        "temp_file_path": str(upload),
        "original_name": "123456789.session",
    }
    settings = MagicMock()
    settings.storage_dir = tmp_path

    with (
        patch("app.handlers.files.user_language", return_value="en"),
        patch(
            "app.handlers.files.process_session_to_tdata_conversion",
            new_callable=AsyncMock,
            return_value=SessionToTdataResult(1, 1, 0, output),
        ),
        patch("app.handlers.files.update_progress_bar", new_callable=AsyncMock),
    ):
        await process_quick_action(callback, MagicMock(), state, settings, MagicMock())

    callback.message.answer_document.assert_awaited_once()
    assert not upload.exists()
    assert not output.exists()
    state.clear.assert_awaited_once()


@pytest.mark.asyncio
async def test_quick_account_to_txt_uses_report_schema_and_cleans(
    tmp_path: Path,
) -> None:
    upload = tmp_path / "123456789.session"
    upload.write_bytes(b"session")
    output = tmp_path / "account_txt.zip"
    output.write_bytes(b"zip")
    callback = MagicMock(spec=CallbackQuery)
    callback.data = "quick:account_to_txt"
    callback.from_user = MagicMock(id=123)
    callback.answer = AsyncMock()
    callback.message = MagicMock(spec=Message)
    callback.message.edit_text = AsyncMock(return_value=callback.message)
    callback.message.answer_document = AsyncMock()
    state = AsyncMock(spec=FSMContext)
    state.get_data.return_value = {
        "temp_file_path": str(upload),
        "original_name": "123456789.session",
    }
    settings = MagicMock()
    settings.storage_dir = tmp_path
    settings.api_credential_list = []

    with (
        patch("app.handlers.files.user_language", return_value="en"),
        patch(
            "app.handlers.files.process_account_to_txt",
            new_callable=AsyncMock,
            return_value=AccountTxtResult(1, 1, 0, 0, output),
        ),
    ):
        await process_quick_action(callback, MagicMock(), state, settings, MagicMock())

    callback.message.answer_document.assert_awaited_once()
    report = callback.message.edit_text.await_args_list[-1].args[0]
    assert "Account → Txt Report" in report
    assert not upload.exists()
    assert not output.exists()
    state.clear.assert_awaited_once()


@pytest.mark.asyncio
async def test_quick_reset_2fa_renders_pending_without_key_error(
    tmp_path: Path,
) -> None:
    upload = tmp_path / "account.session"
    upload.write_bytes(b"session")
    callback = MagicMock(spec=CallbackQuery)
    callback.data = "quick:reset_2fa"
    callback.from_user = MagicMock(id=123)
    callback.answer = AsyncMock()
    callback.message = MagicMock(spec=Message)
    callback.message.edit_text = AsyncMock(return_value=callback.message)
    callback.message.answer_document = AsyncMock()
    state = AsyncMock(spec=FSMContext)
    state.get_data.return_value = {
        "temp_file_path": str(upload),
        "original_name": "account.session",
    }
    settings = MagicMock()
    settings.storage_dir = tmp_path
    settings.api_credential_list = [(123, "hash")]

    with (
        patch("app.handlers.files.user_language", return_value="en"),
        patch(
            "app.handlers.files.process_reset_2fa",
            new_callable=AsyncMock,
            return_value=TwoFactorResult(
                total=1,
                success=0,
                failed=0,
                pending=1,
            ),
        ),
    ):
        await process_quick_action(callback, MagicMock(), state, settings, MagicMock())

    final_text = callback.message.edit_text.await_args_list[-1].args[0]
    assert "1 pending" in final_text
    assert not upload.exists()
    state.clear.assert_awaited_once()
