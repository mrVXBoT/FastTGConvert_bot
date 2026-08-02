import sqlite3
import zipfile
from pathlib import Path
from unittest.mock import AsyncMock, patch

import pytest

from app.keyboards import account_txt_result_menu, main_menu
from app.locales import ACCOUNT_TO_TXT_MESSAGES, ACCOUNT_TO_TXT_PROMPTS, LANGUAGES
from app.services.account_to_txt import (
    AccountProfile,
    process_account_to_txt,
    render_account_line,
)


def _make_session(path: Path) -> None:
    with sqlite3.connect(path) as conn:
        conn.execute(
            "CREATE TABLE sessions (dc_id integer primary key, server_address text, port integer, auth_key blob, takeout_id integer)"
        )
        conn.execute(
            "INSERT INTO sessions VALUES (2, '149.154.167.50', 443, ?, 0)",
            (b"a" * 256,),
        )


def test_render_account_line_matches_reference_format() -> None:
    profile = AccountProfile(
        identifier="573118508561",
        phone="+573118508561",
        username="@Over_Replyz",
        full_name="Echo > Null",
        user_id=1234567890,
    )
    assert render_account_line(profile) == (
        "573118508561|+573118508561|@Over_Replyz|Echo > Null|1234567890"
    )


def test_render_account_line_sanitizes_delimiters() -> None:
    profile = AccountProfile("1234567", "+1234567", "@a|b", "A\nB", 1)
    line = render_account_line(profile)
    assert line.count("|") == 4
    assert "\n" not in line


@pytest.mark.asyncio
async def test_process_single_session_creates_reference_txt(tmp_path: Path) -> None:
    uploaded = tmp_path / "random.session"
    _make_session(uploaded)
    profile = AccountProfile(
        identifier="573118508561",
        phone="+573118508561",
        username="@Over_Replyz",
        full_name="Echo > Null",
        user_id=1234567890,
    )

    with patch(
        "app.services.account_to_txt.fetch_account_profile",
        new=AsyncMock(return_value=("active", profile)),
    ):
        result = await process_account_to_txt(
            uploaded,
            tmp_path / "outbox",
            [(1, "hash")],
            original_name="573118508561.session",
        )

    assert (result.total, result.active, result.invalid_converted, result.failed) == (
        1,
        1,
        0,
        0,
    )
    assert result.output_zip_path is not None
    with zipfile.ZipFile(result.output_zip_path) as archive:
        assert archive.namelist() == ["573118508561.txt"]
        assert archive.read("573118508561.txt").decode().strip() == render_account_line(
            profile
        )


@pytest.mark.asyncio
async def test_process_zip_counts_active_invalid_and_failed(tmp_path: Path) -> None:
    sessions: list[Path] = []
    for name in ("1111111.session", "2222222.session", "3333333.session"):
        path = tmp_path / name
        _make_session(path)
        sessions.append(path)

    archive_path = tmp_path / "accounts.zip"
    with zipfile.ZipFile(archive_path, "w") as archive:
        for path in sessions:
            archive.write(path, arcname=path.name)

    responses = [
        (
            "active",
            AccountProfile("1111111", "+1111111", "@one", "One", 11),
        ),
        (
            "invalid",
            AccountProfile("2222222", "+2222222", "N/A", "N/A", 0),
        ),
        ("failed", None),
    ]
    with patch(
        "app.services.account_to_txt.fetch_account_profile",
        new=AsyncMock(side_effect=responses),
    ):
        result = await process_account_to_txt(
            archive_path, tmp_path / "outbox", [(1, "hash")]
        )

    assert result.total == 3
    assert result.active == 1
    assert result.invalid_converted == 1
    assert result.converted == 2
    assert result.failed == 1
    assert result.output_zip_path is not None
    with zipfile.ZipFile(result.output_zip_path) as archive:
        assert sorted(archive.namelist()) == ["1111111.txt", "2222222.txt"]


def test_account_txt_locales_and_keyboards() -> None:
    for language in LANGUAGES:
        assert language in ACCOUNT_TO_TXT_PROMPTS
        messages = ACCOUNT_TO_TXT_MESSAGES[language]
        assert all(
            key in messages
            for key in (
                "converting",
                "title",
                "summary",
                "no_output",
                "btn_total",
                "btn_converted",
                "btn_failed",
            )
        )
        menu = account_txt_result_menu(3, 2, 1, language)
        assert [row[1].text for row in menu.inline_keyboard] == ["3", "2", "1"]

    callbacks = [
        button.callback_data
        for row in main_menu("en").inline_keyboard
        for button in row
    ]
    assert "tool:account_to_txt" in callbacks
