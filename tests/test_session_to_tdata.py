import sqlite3
import tempfile
import zipfile
from pathlib import Path

import pytest

from app.locales import (
    LANGUAGES,
    SESSION_TO_TDATA_MESSAGES,
    SESSION_TO_TDATA_PROMPTS,
)
from app.services.files import UnsafeArchiveError
from app.services.session_to_tdata import (
    _ensure_opentele_patched,
    convert_session_to_tdata,
    process_session_to_tdata_conversion,
)

_ensure_opentele_patched()

from opentele.td import TDesktop  # type: ignore[import-untyped]


def _create_telethon_session(
    dest: Path,
    dc_id: int = 2,
    auth_key: bytes = b"\x01" * 256,
    user_id: int = 123456789,
) -> None:
    with sqlite3.connect(dest) as conn:
        conn.execute("CREATE TABLE version (version integer primary key)")
        conn.execute("INSERT INTO version VALUES (7)")
        conn.execute(
            "CREATE TABLE sessions (dc_id integer primary key, server_address text, port integer, auth_key blob, takeout_id integer)"
        )
        conn.execute(
            "INSERT INTO sessions VALUES (?, '149.154.167.50', 443, ?, 0)",
            (dc_id, auth_key),
        )
        conn.execute(
            "CREATE TABLE entities (id integer primary key, hash integer, username text, phone text, name text, date integer)"
        )
        conn.execute(
            "INSERT INTO entities VALUES (?, 111, 'user', '12345', 'Test', 1600000000)",
            (user_id,),
        )


def _create_pyrogram_session(
    dest: Path,
    dc_id: int = 2,
    user_id: int = 987654321,
    auth_key: bytes = b"\x02" * 256,
) -> None:
    with sqlite3.connect(dest) as conn:
        conn.execute(
            "CREATE TABLE sessions (dc_id INTEGER, test_mode INTEGER, auth_key BLOB, date INTEGER, user_id INTEGER, is_bot INTEGER)"
        )
        conn.execute(
            "INSERT INTO sessions VALUES (?, 0, ?, 1600000000, ?, 0)",
            (dc_id, auth_key, user_id),
        )


@pytest.mark.asyncio
async def test_convert_telethon_session_to_tdata() -> None:
    with tempfile.TemporaryDirectory() as tmp_dir:
        tmp_path = Path(tmp_dir)
        sess_file = tmp_path / "telethon.session"
        _create_telethon_session(sess_file, user_id=555666777)

        tdata_out = tmp_path / "tdata_out"
        success = await convert_session_to_tdata(sess_file, tdata_out)
        assert success is True
        assert (tdata_out / "key_datas").exists()

        # Verify TDesktop binary data loading & account count
        reloaded = TDesktop(str(tdata_out))
        assert reloaded.isLoaded() is True
        assert reloaded.accountsCount > 0


@pytest.mark.asyncio
async def test_convert_pyrogram_session_to_tdata() -> None:
    with tempfile.TemporaryDirectory() as tmp_dir:
        tmp_path = Path(tmp_dir)
        sess_file = tmp_path / "pyro.session"
        _create_pyrogram_session(sess_file, user_id=987654321)

        tdata_out = tmp_path / "tdata_out"
        success = await convert_session_to_tdata(sess_file, tdata_out)
        assert success is True
        assert (tdata_out / "key_datas").exists()

        # Verify TDesktop binary data loading & account count
        reloaded = TDesktop(str(tdata_out))
        assert reloaded.isLoaded() is True
        assert reloaded.accountsCount > 0


@pytest.mark.asyncio
async def test_convert_invalid_auth_key_rejected() -> None:
    with tempfile.TemporaryDirectory() as tmp_dir:
        tmp_path = Path(tmp_dir)

        # 16-byte auth_key (invalid length for Telegram auth_key)
        short_file = tmp_path / "short_key.session"
        _create_telethon_session(short_file, auth_key=b"\x01" * 16)
        assert await convert_session_to_tdata(short_file, tmp_path / "out1") is False

        # 256-byte zeroed auth_key (invalid empty key)
        zero_file = tmp_path / "zero_key.session"
        _create_telethon_session(zero_file, auth_key=b"\x00" * 256)
        assert await convert_session_to_tdata(zero_file, tmp_path / "out2") is False


@pytest.mark.asyncio
async def test_convert_missing_user_id_rejected() -> None:
    with tempfile.TemporaryDirectory() as tmp_dir:
        tmp_path = Path(tmp_dir)
        sess_file = tmp_path / "unnamed.session"

        with sqlite3.connect(sess_file) as conn:
            conn.execute("CREATE TABLE version (version integer primary key)")
            conn.execute("INSERT INTO version VALUES (7)")
            conn.execute(
                "CREATE TABLE sessions (dc_id integer primary key, server_address text, port integer, auth_key blob, takeout_id integer)"
            )
            conn.execute(
                "INSERT INTO sessions VALUES (2, '149.154.167.50', 443, ?, 0)",
                (b"\x01" * 256,),
            )

        # Without entities or user_id or numerical filename, conversion is rejected
        assert await convert_session_to_tdata(sess_file, tmp_path / "out") is False


@pytest.mark.asyncio
async def test_process_session_to_tdata_single_session() -> None:
    with tempfile.TemporaryDirectory() as tmp_dir:
        tmp_path = Path(tmp_dir)
        sess_file = tmp_path / "acc.session"
        _create_telethon_session(sess_file)

        outbox = tmp_path / "outbox"
        res = await process_session_to_tdata_conversion(sess_file, outbox)

        assert res.total == 1
        assert res.converted == 1
        assert res.failed == 0
        assert res.output_zip_path is not None
        assert res.output_zip_path.exists()

        # Check zip contents
        with zipfile.ZipFile(res.output_zip_path, "r") as z:
            names = z.namelist()
            assert any(n.endswith("key_datas") for n in names)


@pytest.mark.asyncio
async def test_process_session_to_tdata_zip_input() -> None:
    with tempfile.TemporaryDirectory() as tmp_dir:
        tmp_path = Path(tmp_dir)
        sess1 = tmp_path / "acc1.session"
        sess2 = tmp_path / "acc2.session"
        _create_telethon_session(sess1)
        _create_pyrogram_session(sess2)

        input_zip = tmp_path / "sessions.zip"
        with zipfile.ZipFile(input_zip, "w") as z:
            z.write(sess1, arcname="acc1.session")
            z.write(sess2, arcname="acc2.session")

        outbox = tmp_path / "outbox"
        res = await process_session_to_tdata_conversion(input_zip, outbox)

        assert res.total == 2
        assert res.converted == 2
        assert res.failed == 0
        assert res.output_zip_path is not None
        assert res.output_zip_path.exists()


@pytest.mark.asyncio
async def test_process_session_to_tdata_zip_slip_rejected() -> None:
    with tempfile.TemporaryDirectory() as tmp_dir:
        tmp_path = Path(tmp_dir)
        input_zip = tmp_path / "bad.zip"
        with zipfile.ZipFile(input_zip, "w") as z:
            z.writestr("../bad.session", b"dummy")

        outbox = tmp_path / "outbox"
        with pytest.raises(UnsafeArchiveError):
            await process_session_to_tdata_conversion(input_zip, outbox)


@pytest.mark.asyncio
async def test_session_to_tdata_localization_all_languages() -> None:
    for lang in LANGUAGES:
        assert lang in SESSION_TO_TDATA_PROMPTS
        assert lang in SESSION_TO_TDATA_MESSAGES
        assert "done" in SESSION_TO_TDATA_MESSAGES[lang]
        assert "converting" in SESSION_TO_TDATA_MESSAGES[lang]
        assert "no_valid_sessions" in SESSION_TO_TDATA_MESSAGES[lang]
