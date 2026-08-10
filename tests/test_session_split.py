import sqlite3
import zipfile
from pathlib import Path
from unittest.mock import AsyncMock, patch

import pytest

from app.keyboards import file_split_choice_menu, file_split_result_menu
from app.locales import LANGUAGES, SPLIT_MESSAGES, SPLIT_PROMPTS
from app.services.files import UnsafeArchiveError
from app.services.session_split import (
    country_for_phone,
    flag_for_phone,
    inspect_session_split,
    process_session_split,
)


def _session(
    path: Path,
    phone: str,
    *,
    user_id: int,
    auth_key: bytes = b"\x11" * 256,
) -> Path:
    with sqlite3.connect(path) as connection:
        connection.execute(
            "CREATE TABLE sessions (dc_id integer primary key, server_address "
            "text, port integer, auth_key blob, takeout_id integer)"
        )
        connection.execute(
            "INSERT INTO sessions VALUES (2, '149.154.167.50', 443, ?, 0)",
            (auth_key,),
        )
        connection.execute(
            "CREATE TABLE entities (id integer primary key, hash integer, "
            "username text, phone text, name text, date integer)"
        )
        connection.execute(
            "INSERT INTO entities VALUES (?, 1, NULL, ?, NULL, 0)",
            (user_id, phone),
        )
    return path


def test_country_detection() -> None:
    assert country_for_phone("+573118508561") == "Colombia"
    assert country_for_phone("+989121234567") == "Iran"
    assert country_for_phone(None) == "Unknown"
    assert country_for_phone("invalid") == "Unknown"


def test_flag_detection() -> None:
    assert flag_for_phone("+573118508561") == "🇨🇴"
    assert flag_for_phone("+989121234567") == "🇮🇷"
    assert flag_for_phone("+2347031234567") == "🇳🇬"
    assert flag_for_phone(None) is None
    assert flag_for_phone("invalid") is None


@pytest.mark.asyncio
async def test_inspect_session_and_zip(tmp_path: Path) -> None:
    first = _session(tmp_path / "573118508561.session", "573118508561", user_id=1)
    second = _session(tmp_path / "989121234567.session", "989121234567", user_id=2)
    archive_path = tmp_path / "sessions.zip"
    with zipfile.ZipFile(archive_path, "w") as archive:
        archive.write(first, first.name)
        archive.write(second, second.name)

    assert await inspect_session_split(first) == 1
    assert await inspect_session_split(archive_path) == 2


@pytest.mark.asyncio
async def test_split_by_quantity(tmp_path: Path) -> None:
    sessions = [
        _session(
            tmp_path / f"57311850856{index}.session",
            f"57311850856{index}",
            user_id=index,
        )
        for index in range(1, 4)
    ]
    archive_path = tmp_path / "input.zip"
    with zipfile.ZipFile(archive_path, "w") as archive:
        for session in sessions:
            archive.write(session, session.name)

    result = await process_session_split(
        archive_path, "quantity", tmp_path / "out", quantity=2
    )

    assert (result.total, result.split, result.failed, result.groups) == (3, 3, 0, 2)
    assert [output.filename for output in result.outputs] == [
        "Part001_2.zip",
        "Part002_1.zip",
    ]
    with zipfile.ZipFile(result.outputs[0].path) as archive:
        assert archive.namelist() == [
            "573118508561.session",
            "573118508562.session",
        ]


@pytest.mark.asyncio
async def test_split_by_country(tmp_path: Path) -> None:
    colombia = _session(tmp_path / "573118508561.session", "573118508561", user_id=1)
    iran = _session(tmp_path / "989121234567.session", "989121234567", user_id=2)
    archive_path = tmp_path / "countries.zip"
    with zipfile.ZipFile(archive_path, "w") as archive:
        archive.write(colombia, colombia.name)
        archive.write(iran, iran.name)

    result = await process_session_split(archive_path, "country", tmp_path / "out")

    assert (result.total, result.split, result.failed, result.groups) == (2, 2, 0, 2)
    assert {output.filename for output in result.outputs} == {
        "Colombia_1.zip",
        "Iran_1.zip",
    }
    assert {output.label for output in result.outputs} == {"Colombia", "Iran"}
    assert {output.flag for output in result.outputs} == {"🇨🇴", "🇮🇷"}


@pytest.mark.asyncio
async def test_invalid_session_is_counted_as_failed(tmp_path: Path) -> None:
    valid = _session(tmp_path / "valid.session", "573118508561", user_id=1)
    invalid = _session(
        tmp_path / "invalid.session",
        "989121234567",
        user_id=2,
        auth_key=b"short",
    )
    archive_path = tmp_path / "mixed.zip"
    with zipfile.ZipFile(archive_path, "w") as archive:
        archive.write(valid, valid.name)
        archive.write(invalid, invalid.name)

    assert await inspect_session_split(archive_path) == 2
    result = await process_session_split(
        archive_path, "quantity", tmp_path / "out", quantity=10
    )

    assert (result.total, result.split, result.failed, result.groups) == (2, 1, 1, 1)


@pytest.mark.asyncio
async def test_zip_slip_is_rejected(tmp_path: Path) -> None:
    archive_path = tmp_path / "unsafe.zip"
    with zipfile.ZipFile(archive_path, "w") as archive:
        archive.writestr("../escape.session", b"unsafe")

    with pytest.raises(UnsafeArchiveError, match="zip_unsafe_path"):
        await inspect_session_split(archive_path)


@pytest.mark.asyncio
async def test_split_by_country_with_credentials_unpacks_full_profile(
    tmp_path: Path,
) -> None:
    session = _session(tmp_path / "573118508561.session", "573118508561", user_id=1)

    with patch(
        "app.services.session_split._live_probe",
        new_callable=AsyncMock,
        return_value=(True, "+573118508561"),
    ):
        result = await process_session_split(
            session,
            "country",
            tmp_path / "out",
            [(12345, "hash")],
        )

    assert (result.total, result.split, result.failed, result.groups) == (1, 1, 0, 1)
    assert result.outputs[0].flag == "🇨🇴"


@pytest.mark.asyncio
async def test_quantity_split_with_credentials_only_counts_authorized(
    tmp_path: Path,
) -> None:
    good = _session(tmp_path / "573118508561.session", "573118508561", user_id=1)
    dead = _session(tmp_path / "989121234567.session", "989121234567", user_id=2)
    archive_path = tmp_path / "mixed.zip"
    with zipfile.ZipFile(archive_path, "w") as archive:
        archive.write(good, good.name)
        archive.write(dead, dead.name)

    async def fake_probe(path: Path, _credentials: object):
        if path.name == "989121234567.session":
            return False, None
        return True, "+573118508561"

    with patch(
        "app.services.session_split._live_probe",
        new_callable=AsyncMock,
        side_effect=fake_probe,
    ):
        result = await process_session_split(
            archive_path, "quantity", tmp_path / "out", [(12345, "hash")], quantity=10
        )

    assert (result.total, result.split, result.failed, result.groups) == (2, 1, 1, 1)
    with zipfile.ZipFile(result.outputs[0].path) as archive:
        assert archive.namelist() == ["573118508561.session"]


@pytest.mark.asyncio
async def test_quantity_split_without_credentials_stays_offline(
    tmp_path: Path,
) -> None:
    good = _session(tmp_path / "573118508561.session", "573118508561", user_id=1)
    result = await process_session_split(
        good, "quantity", tmp_path / "out", quantity=10
    )
    assert (result.total, result.split, result.failed, result.groups) == (1, 1, 0, 1)


def test_split_locales_and_keyboards() -> None:
    required = {
        "choose_type",
        "btn_country",
        "btn_quantity",
        "btn_cancel",
        "quantity_prompt",
        "country_completed",
        "quantity_completed",
        "caption_country",
        "caption_part",
        "no_sessions",
        "invalid_quantity",
        "btn_total",
        "btn_split",
        "btn_failed",
    }
    for language in LANGUAGES:
        assert "/cancel" not in SPLIT_PROMPTS[language]
        assert required <= SPLIT_MESSAGES[language].keys()
        choice = file_split_choice_menu(language)
        result = file_split_result_menu(3, 2, 1, language)
        assert len(choice.inline_keyboard) == 3
        assert len(result.inline_keyboard) == 3
