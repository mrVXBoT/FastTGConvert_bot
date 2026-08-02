import json
import sqlite3
import zipfile
from pathlib import Path
from unittest.mock import AsyncMock, patch

import pytest

from app.keyboards import main_menu, session_json_result_menu
from app.locales import LANGUAGES, SESSION_TO_JSON_MESSAGES, SESSION_TO_JSON_PROMPTS
from app.services.account_to_txt import AccountProfile
from app.services.session_to_json import process_session_to_json, render_session_json


def _make_session(path: Path, dc_id: int = 2) -> None:
    with sqlite3.connect(path) as conn:
        conn.execute(
            "CREATE TABLE sessions (dc_id integer primary key, server_address text, port integer, auth_key blob, takeout_id integer)"
        )
        conn.execute(
            "INSERT INTO sessions VALUES (?, '149.154.167.50', 443, ?, 0)",
            (dc_id, b"a" * 256),
        )


def test_render_session_json_matches_reference_schema() -> None:
    profile = AccountProfile(
        identifier="573118508561",
        phone="+573118508561",
        username="@Over_Replyz",
        full_name="Echo > Null",
        user_id=1234567890,
        premium=True,
    )
    payload = json.loads(
        render_session_json(
            profile,
            dc_id=2,
            server_address="149.154.167.50",
            authorized=True,
        )
    )
    assert list(payload) == [
        "name",
        "phone",
        "username",
        "full_name",
        "user_id",
        "premium",
        "dc_id",
        "server_address",
        "authorized",
    ]
    assert payload == {
        "name": "573118508561",
        "phone": "+573118508561",
        "username": "@Over_Replyz",
        "full_name": "Echo > Null",
        "user_id": 1234567890,
        "premium": True,
        "dc_id": 2,
        "server_address": "149.154.167.50",
        "authorized": True,
    }


@pytest.mark.asyncio
async def test_process_single_session_creates_reference_json(tmp_path: Path) -> None:
    uploaded = tmp_path / "random.session"
    _make_session(uploaded)
    profile = AccountProfile(
        "573118508561",
        "+573118508561",
        "@Over_Replyz",
        "Echo > Null",
        1234567890,
        True,
    )
    with patch(
        "app.services.session_to_json.fetch_account_profile",
        new=AsyncMock(return_value=("active", profile)),
    ):
        result = await process_session_to_json(
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
        assert archive.namelist() == ["573118508561.json"]
        payload = json.loads(archive.read("573118508561.json"))
        assert payload["authorized"] is True
        assert payload["premium"] is True
        assert payload["dc_id"] == 2


@pytest.mark.asyncio
async def test_process_zip_counts_all_statuses(tmp_path: Path) -> None:
    paths: list[Path] = []
    for name in ("1111111.session", "2222222.session", "3333333.session"):
        path = tmp_path / name
        _make_session(path)
        paths.append(path)

    input_zip = tmp_path / "sessions.zip"
    with zipfile.ZipFile(input_zip, "w") as archive:
        for path in paths:
            archive.write(path, arcname=path.name)

    responses = [
        ("active", AccountProfile("1111111", "+1111111", "@one", "One", 1)),
        (
            "invalid",
            AccountProfile("2222222", "+2222222", "N/A", "N/A", 0),
        ),
        ("failed", None),
    ]
    with patch(
        "app.services.session_to_json.fetch_account_profile",
        new=AsyncMock(side_effect=responses),
    ):
        result = await process_session_to_json(
            input_zip, tmp_path / "outbox", [(1, "hash")]
        )

    assert result.total == 3
    assert result.active == 1
    assert result.invalid_converted == 1
    assert result.converted == 2
    assert result.failed == 1
    assert [entry.authorized for entry in result.entries] == [True, False]
    assert result.output_zip_path is not None
    with zipfile.ZipFile(result.output_zip_path) as archive:
        assert sorted(archive.namelist()) == ["1111111.json", "2222222.json"]


def test_session_json_locales_and_keyboards() -> None:
    for language in LANGUAGES:
        assert language in SESSION_TO_JSON_PROMPTS
        messages = SESSION_TO_JSON_MESSAGES[language]
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
        menu = session_json_result_menu(3, 2, 1, language)
        assert [row[1].text for row in menu.inline_keyboard] == ["3", "2", "1"]

    callbacks = [
        button.callback_data
        for row in main_menu("en").inline_keyboard
        for button in row
    ]
    assert "tool:session_to_json" in callbacks
