import asyncio
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
from app.services.jobs import JobCancelled, JobProgress


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
        premium=True,
        dc_id=2,
        two_fa=True,
        registered="2023-05-01",
    )
    assert render_account_line(profile) == (
        "573118508561|+573118508561|@Over_Replyz|Echo > Null|1234567890|1|2|1|2023-05-01"
    )


def test_render_account_line_sanitizes_delimiters() -> None:
    profile = AccountProfile("1234567", "+1234567", "@a|b", "A\nB", 1)
    line = render_account_line(profile)
    assert line.count("|") == 8
    assert "\n" not in line
    assert line.endswith("|0|N/A|N/A|N/A")


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
        dc_id=2,
    )

    with patch(
        "app.services.account_to_txt.fetch_account_profile",
        new=AsyncMock(return_value=("active", profile, "")),
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
        assert archive.namelist() == ["phones.txt", "573118508561.txt"]
        assert archive.read("573118508561.txt").decode().strip() == render_account_line(
            profile
        )
        assert archive.read("phones.txt").decode().strip() == "+573118508561"
    assert result.phones_path is not None
    assert result.phones_path.read_text(encoding="utf-8").strip() == "+573118508561"
    assert result.status_path is not None
    assert (
        result.status_path.read_text(encoding="utf-8").strip()
        == "+573118508561 | ✅ active"
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
        ("active", AccountProfile("1111111", "+1111111", "@one", "One", 11), ""),
        ("invalid", AccountProfile("2222222", "+2222222", "N/A", "N/A", 0), "unauthorized"),
        ("failed", None, "no_credentials"),
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
    assert result.converted == 1
    assert result.failed == 1
    assert [entry.status for entry in result.entries] == [
        "active",
        "invalid",
        "failed",
    ]
    assert result.output_zip_path is not None
    with zipfile.ZipFile(result.output_zip_path) as archive:
        assert sorted(archive.namelist()) == [
            "1111111.txt",
            "Invalid/2222222.txt",
            "phones.txt",
        ]
        assert archive.read("Invalid/2222222.txt").decode().strip() == render_account_line(
            AccountProfile("2222222", "+2222222", "N/A", "N/A", 0, dc_id=2)
        )
        assert archive.read("phones.txt").decode().strip().splitlines() == [
            "+1111111",
            "+2222222",
            "+3333333",
        ]
    assert result.phones_path is not None
    assert result.phones_path.read_text(encoding="utf-8").strip().splitlines() == [
        "+1111111",
        "+2222222",
        "+3333333",
    ]
    assert result.status_path is not None
    assert result.status_path.read_text(encoding="utf-8").strip().splitlines() == [
        "+1111111 | ✅ active",
        "+2222222 | ⚠️ unauthorized",
        "+3333333 | ❌ no_credentials",
    ]


@pytest.mark.asyncio
async def test_sidecar_password_sets_two_fa_for_invalid(tmp_path: Path) -> None:
    uploaded = tmp_path / "1234567.session"
    _make_session(uploaded)
    sidecar = tmp_path / "password.txt"
    sidecar.write_text("s3cret\n", encoding="utf-8")

    archive_path = tmp_path / "accounts.zip"
    with zipfile.ZipFile(archive_path, "w") as archive:
        archive.write(uploaded, arcname="1234567.session")
        archive.write(sidecar, arcname="password.txt")

    profile = AccountProfile("1234567", "+1234567", "N/A", "N/A", 0)
    with patch(
        "app.services.account_to_txt.fetch_account_profile",
        new=AsyncMock(return_value=("invalid", profile, "unauthorized")),
    ):
        result = await process_account_to_txt(
            archive_path, tmp_path / "outbox", [(1, "hash")]
        )

    assert result.invalid_converted == 1
    assert result.output_zip_path is not None
    with zipfile.ZipFile(result.output_zip_path) as archive:
        line = archive.read("Invalid/1234567.txt").decode().strip()
    assert line.split("|")[7] == "1"


@pytest.mark.asyncio
async def test_cancel_event_raises_job_cancelled(tmp_path: Path) -> None:
    uploaded = tmp_path / "1234567.session"
    _make_session(uploaded)

    progress = JobProgress()
    cancel_event = asyncio.Event()
    cancel_event.set()

    with (
        patch(
            "app.services.account_to_txt.fetch_account_profile",
            new=AsyncMock(return_value=("active", AccountProfile("1", "1", "N/A", "N/A", 0), "")),
        ),
        pytest.raises(JobCancelled),
    ):
        await process_account_to_txt(
            uploaded,
            tmp_path / "outbox",
            [(1, "hash")],
            progress=progress,
            cancel_event=cancel_event,
        )


@pytest.mark.asyncio
async def test_txt_input_is_ignored(tmp_path: Path) -> None:
    uploaded = tmp_path / "accounts.txt"
    uploaded.write_text("1|2|3", encoding="utf-8")

    result = await process_account_to_txt(
        uploaded, tmp_path / "outbox", [(1, "hash")], original_name="accounts.txt"
    )

    assert result.total == 0
    assert result.output_zip_path is None


@pytest.mark.asyncio
async def test_probes_run_concurrently_but_bounded(tmp_path: Path) -> None:
    """Per-session network probes must overlap (not run one-by-one) and never
    exceed the module concurrency ceiling."""
    sessions = []
    for i in range(6):
        path = tmp_path / f"sess{i}.session"
        _make_session(path)
        sessions.append(path)

    archive_path = tmp_path / "accounts.zip"
    with zipfile.ZipFile(archive_path, "w") as archive:
        for path in sessions:
            archive.write(path, arcname=path.name)

    active = 0
    max_active = 0
    lock = asyncio.Lock()

    async def slow_probe(*_args, **_kwargs):
        nonlocal active, max_active
        async with lock:
            active += 1
            max_active = max(max_active, active)
        await asyncio.sleep(0.05)
        async with lock:
            active -= 1
        return (
            "active",
            AccountProfile(f"sess{_args[0].stem}", "+1", "N/A", "N/A", 0),
            "",
        )

    from app.services.account_to_txt import _PROBE_CONCURRENCY

    with patch(
        "app.services.account_to_txt.fetch_account_profile",
        new=slow_probe,
    ):
        result = await process_account_to_txt(
            archive_path, tmp_path / "outbox", [(1, "hash")]
        )

    assert result.active == 6
    assert max_active >= 2, "probes ran strictly one-by-one (no overlap)"
    assert max_active <= _PROBE_CONCURRENCY, "concurrency exceeded the ceiling"


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
                "btn_retry",
                "btn_home",
                "caption",
                "cancelled",
                "more",
            )
        )
        menu = account_txt_result_menu(3, 2, 1, language)
        assert [row[1].text for row in menu.inline_keyboard[:3]] == ["3", "2", "1"]

    callbacks = [
        button.callback_data
        for row in main_menu("en").inline_keyboard
        for button in row
    ]
    assert "tool:account_to_txt" in callbacks
