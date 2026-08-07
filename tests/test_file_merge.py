import json
import sqlite3
import zipfile
from pathlib import Path
from unittest.mock import AsyncMock, patch

import pytest
from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery, Message

from app.handlers.start import callback_flow_cancel, clear_state_and_file
from app.keyboards import file_merge_choice_menu, file_merge_result_menu
from app.locales import FILE_MERGE_MESSAGES, FILE_MERGE_PROMPTS, LANGUAGES
from app.services.account_to_txt import AccountProfile
from app.services.file_merge import (
    extract_account_identifier,
    inspect_mergeable_sessions,
    process_file_merge,
)


def _create_session(
    path: Path,
    *,
    user_id: int = 8886120375,
    phone: str = "573118508561",
    auth_key: bytes = b"\x07" * 256,
) -> Path:
    with sqlite3.connect(path) as conn:
        conn.execute("CREATE TABLE version (version integer primary key)")
        conn.execute("INSERT INTO version VALUES (7)")
        conn.execute(
            "CREATE TABLE sessions (dc_id integer primary key, server_address"
            " text, port integer, auth_key blob, takeout_id integer)"
        )
        conn.execute(
            "INSERT INTO sessions VALUES (2, '149.154.167.50', 443, ?, 0)",
            (auth_key,),
        )
        conn.execute(
            "CREATE TABLE entities (id integer primary key, hash integer,"
            " username text, phone text, name text, date integer)"
        )
        conn.execute(
            "INSERT INTO entities VALUES (?, 1, 'testuser', ?, 'Test', 1600000000)",
            (user_id, phone),
        )
    return path


@pytest.fixture
def dummy_session(tmp_path: Path) -> Path:
    return _create_session(tmp_path / "573118508561.session")


def test_extract_account_identifier(dummy_session: Path):
    identifier, uid, phone = extract_account_identifier(dummy_session)
    assert identifier == "+573118508561"
    assert uid == 8886120375
    assert phone == "573118508561"


@pytest.mark.asyncio
async def test_inspect_mergeable_sessions_single(dummy_session: Path):
    sessions = await inspect_mergeable_sessions(dummy_session)
    assert len(sessions) == 1
    assert sessions[0] == dummy_session


@pytest.mark.asyncio
async def test_inspect_mergeable_sessions_zip(dummy_session: Path, tmp_path: Path):
    zip_path = tmp_path / "sessions_input.zip"
    with zipfile.ZipFile(zip_path, "w") as zf:
        zf.write(dummy_session, arcname="573118508561.session")

    sessions = await inspect_mergeable_sessions(zip_path)
    assert len(sessions) == 1


@pytest.mark.asyncio
async def test_inspection_does_not_double_count_converted_tdata(
    dummy_session: Path, tmp_path: Path
):
    zip_path = tmp_path / "mixed.zip"
    with zipfile.ZipFile(zip_path, "w") as archive:
        archive.write(dummy_session, arcname=dummy_session.name)
        archive.writestr("tdata/key_datas", b"marker")

    async def fake_convert(_tdata: Path, output: Path) -> list[Path]:
        output.mkdir(parents=True, exist_ok=True)
        return [
            _create_session(
                output / "session_222222222.session",
                user_id=222222222,
                phone="989121234567",
            )
        ]

    with patch(
        "app.services.file_merge.convert_tdata_dir_to_sessions",
        new_callable=AsyncMock,
        side_effect=fake_convert,
    ):
        sessions = await inspect_mergeable_sessions(zip_path)

    assert len(sessions) == 2


@pytest.mark.asyncio
async def test_short_auth_key_is_not_mergeable(tmp_path: Path):
    invalid = _create_session(tmp_path / "invalid.session", auth_key=b"too-short")

    assert await inspect_mergeable_sessions(invalid) == []


@pytest.mark.asyncio
async def test_process_file_merge_multi_type(dummy_session: Path, tmp_path: Path):
    out_dir = tmp_path / "out"
    res = await process_file_merge(dummy_session, "multi_type", out_dir)
    assert res.total == 1
    assert res.merged == 1
    assert res.failed == 0
    assert res.output_path is not None
    assert res.output_path.exists()
    assert res.output_path.name.startswith("merged_all")

    with zipfile.ZipFile(res.output_path, "r") as zf:
        names = zf.namelist()
        assert "+573118508561.session" in names


@pytest.mark.asyncio
async def test_process_file_merge_session_json_tdata(
    dummy_session: Path, tmp_path: Path
):
    out_dir = tmp_path / "out"
    profile = AccountProfile(
        identifier="573118508561",
        phone="+573118508561",
        username="@Over_Replyz",
        full_name="Echo > Null",
        user_id=8886120375,
        premium=False,
    )

    async def fake_tdata(
        _session: Path, target: Path, *, credentials: object = None
    ) -> bool:
        target.mkdir(parents=True)
        (target / "key_datas").write_bytes(b"valid")
        (target / "account_data").write_bytes(b"data")
        return True

    with (
        patch(
            "app.services.file_merge.fetch_account_profile",
            new_callable=AsyncMock,
            return_value=("active", profile, ""),
        ),
        patch(
            "app.services.file_merge.convert_session_to_tdata",
            new_callable=AsyncMock,
            side_effect=fake_tdata,
        ),
    ):
        res = await process_file_merge(
            dummy_session,
            "session_json_tdata",
            out_dir,
            [(12345, "hash")],
        )
        assert res.total == 1
        assert res.merged == 1
        assert res.failed == 0
        assert res.output_path is not None
        assert res.output_path.exists()
        assert res.output_path.name.startswith("merge_json_tdata")

        with zipfile.ZipFile(res.output_path, "r") as zf:
            names = zf.namelist()
            assert "573118508561.session" in names
            assert "573118508561.json" in names
            assert "tdata/key_datas" in names
            payload = json.loads(zf.read("573118508561.json"))
            assert payload == {
                "name": "573118508561",
                "phone": "+573118508561",
                "username": "@Over_Replyz",
                "full_name": "Echo > Null",
                "user_id": 8886120375,
                "premium": False,
                "dc_id": 2,
                "server_address": "149.154.167.50",
                "authorized": True,
                "two_fa": None,
                "registered": "N/A",
            }


@pytest.mark.asyncio
async def test_session_json_tdata_failure_is_not_reported_as_success(
    dummy_session: Path, tmp_path: Path
):
    profile = AccountProfile("573118508561", "+573118508561", "N/A", "N/A", 8886120375)
    with (
        patch(
            "app.services.file_merge.fetch_account_profile",
            new_callable=AsyncMock,
            return_value=("active", profile, ""),
        ),
        patch(
            "app.services.file_merge.convert_session_to_tdata",
            new_callable=AsyncMock,
            return_value=False,
        ),
    ):
        result = await process_file_merge(
            dummy_session, "session_json_tdata", tmp_path / "out", [(1, "hash")]
        )

    assert (result.total, result.merged, result.failed) == (1, 0, 1)
    assert result.output_path is None
    assert result.entries[0].success is False


@pytest.mark.asyncio
async def test_multi_account_tdata_uses_separate_zip_folders(tmp_path: Path):
    first = _create_session(tmp_path / "first.session")
    second = _create_session(
        tmp_path / "second.session", user_id=222222222, phone="989121234567"
    )
    source_zip = tmp_path / "input.zip"
    with zipfile.ZipFile(source_zip, "w") as archive:
        archive.write(first, first.name)
        archive.write(second, second.name)

    profiles = {
        "first.session": AccountProfile(
            "573118508561", "+573118508561", "@one", "One", 8886120375
        ),
        "second.session": AccountProfile(
            "989121234567", "+989121234567", "@two", "Two", 222222222
        ),
    }

    async def fake_profile(path: Path, _credentials: object):
        return "active", profiles[path.name], ""

    async def fake_tdata(
        _session: Path, target: Path, *, credentials: object = None
    ) -> bool:
        target.mkdir(parents=True)
        (target / "key_datas").write_bytes(b"valid")
        return True

    with (
        patch(
            "app.services.file_merge.fetch_account_profile",
            new_callable=AsyncMock,
            side_effect=fake_profile,
        ),
        patch(
            "app.services.file_merge.convert_session_to_tdata",
            new_callable=AsyncMock,
            side_effect=fake_tdata,
        ),
    ):
        result = await process_file_merge(
            source_zip, "session_json_tdata", tmp_path / "out", [(1, "hash")]
        )

    assert (result.total, result.merged, result.failed) == (2, 2, 0)
    assert result.output_path is not None
    with zipfile.ZipFile(result.output_path) as archive:
        names = set(archive.namelist())
    assert "573118508561/tdata/key_datas" in names
    assert "989121234567/tdata/key_datas" in names
    assert "573118508561/573118508561.json" in names
    assert "989121234567/989121234567.json" in names


@pytest.mark.asyncio
async def test_cancel_cleans_file_merge_upload(tmp_path: Path):
    upload = tmp_path / "upload.zip"
    upload.write_bytes(b"temporary")
    state = AsyncMock()
    state.get_data.return_value = {"temp_file_path": str(upload)}

    await clear_state_and_file(state)

    assert not upload.exists()
    state.clear.assert_awaited_once()


@pytest.mark.asyncio
async def test_clear_state_and_file_removes_temp_dir(tmp_path: Path):
    upload = tmp_path / "upload.session"
    upload.write_bytes(b"temporary")
    work_dir = tmp_path / "work"
    work_dir.mkdir()
    (work_dir / "inner.session").write_bytes(b"x")
    state = AsyncMock()
    state.get_data.return_value = {
        "temp_file_path": str(upload),
        "temp_dir": str(work_dir),
    }

    await clear_state_and_file(state)

    assert not upload.exists()
    assert not work_dir.exists()
    state.clear.assert_awaited_once()


@pytest.mark.asyncio
async def test_clear_state_and_file_removes_file_path(tmp_path: Path):
    saved = tmp_path / "saved.session"
    saved.write_bytes(b"secret")
    state = AsyncMock()
    state.get_data.return_value = {"file_path": str(saved)}

    await clear_state_and_file(state)

    assert not saved.exists()
    state.clear.assert_awaited_once()


@pytest.mark.asyncio
async def test_flow_cancel_callback_cleans_state_and_returns_menu(tmp_path: Path):
    upload = tmp_path / "upload.session"
    upload.write_bytes(b"temporary")
    work_dir = tmp_path / "work"
    work_dir.mkdir()
    state = AsyncMock(spec=FSMContext)
    state.get_data.return_value = {
        "temp_file_path": str(upload),
        "temp_dir": str(work_dir),
    }
    callback = AsyncMock(spec=CallbackQuery)
    callback.from_user = AsyncMock(id=123)
    callback.message = AsyncMock(spec=Message)
    callback.message.edit_text = AsyncMock()
    callback.answer = AsyncMock()

    with (
        patch("app.handlers.start.user_language", return_value="en"),
        patch("app.handlers.start.action_message", return_value="canceled"),
        patch("app.handlers.start.main_menu", return_value="menu"),
    ):
        await callback_flow_cancel(callback, state, AsyncMock())

    assert not upload.exists()
    assert not work_dir.exists()
    state.clear.assert_awaited_once()
    callback.answer.assert_awaited_once()
    callback.message.edit_text.assert_awaited_once()


def test_file_merge_locales_and_keyboards():
    for lang in LANGUAGES:
        assert lang in FILE_MERGE_PROMPTS
        assert "/cancel" not in FILE_MERGE_PROMPTS[lang]
        assert lang in FILE_MERGE_MESSAGES

        kb_choice = file_merge_choice_menu(lang)
        assert len(kb_choice.inline_keyboard) == 3

        kb_res = file_merge_result_menu(1, 1, 0, lang)
        assert len(kb_res.inline_keyboard) == 3


def test_direct_file_locales_and_keyboards():
    from app.keyboards import main_menu, quick_action_menu
    from app.locales import DIRECT_FILE_MESSAGES, DIRECT_FILE_PROMPTS

    for lang in LANGUAGES:
        assert lang in DIRECT_FILE_PROMPTS
        assert lang in DIRECT_FILE_MESSAGES
        assert "{filename}" in DIRECT_FILE_PROMPTS[lang]

        kb_quick = quick_action_menu(lang)
        kb_main = main_menu(lang)
        assert [
            [button.text for button in row] for row in kb_quick.inline_keyboard
        ] == [[button.text for button in row] for row in kb_main.inline_keyboard]
        callbacks = {
            btn.callback_data for row in kb_quick.inline_keyboard for btn in row
        }
        assert {
            "quick:session_check",
            "quick:spam_check",
            "quick:read_otp",
            "quick:check_contacts",
            "quick:session_to_tdata",
            "quick:tdata_to_session",
            "quick:session_to_json",
            "quick:account_to_txt",
            "quick:file_split",
            "quick:file_merge",
            "quick:change_2fa",
            "quick:disable_2fa",
            "quick:reset_2fa",
        } <= callbacks
