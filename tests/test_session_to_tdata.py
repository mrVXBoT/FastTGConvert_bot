import asyncio
import sqlite3
import tempfile
import zipfile
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from telethon.errors import AuthKeyUnregisteredError  # type: ignore[import-untyped]

from app.locales import (
    LANGUAGES,
    SESSION_TO_TDATA_MESSAGES,
    SESSION_TO_TDATA_PROMPTS,
)
from app.services.files import UnsafeArchiveError
from app.services.jobs import JobCancelled, JobProgress
from app.services.session_to_tdata import (
    _ensure_opentele_patched,
    _inspect_session,
    _live_session_probe,
    convert_session_to_tdata,
    live_failure_label,
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
        assert [(entry.name, entry.ok) for entry in res.entries] == [("acc", True)]

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
        assert all(entry.ok for entry in res.entries)


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
async def test_process_session_to_tdata_job_cancelled() -> None:
    with tempfile.TemporaryDirectory() as tmp_dir:
        tmp_path = Path(tmp_dir)
        sess_file = tmp_path / "acc.session"
        _create_telethon_session(sess_file)

        progress = JobProgress()
        cancel_event = asyncio.Event()
        cancel_event.set()

        with pytest.raises(JobCancelled):
            await process_session_to_tdata_conversion(
                sess_file, tmp_path / "outbox", progress=progress, cancel_event=cancel_event
            )


def _dead_session_client() -> AsyncMock:
    """Mocked Telethon client whose session was revoked/deactivated server-side."""
    client = AsyncMock()
    client.connect = AsyncMock()
    client.get_me = AsyncMock(
        side_effect=AuthKeyUnregisteredError("AUTH_KEY_UNREGISTERED")
    )
    client.disconnect = AsyncMock()
    return client


def _authorized_probe_client(user_id: int) -> AsyncMock:
    """Mocked Telethon client whose session is live and owned by *user_id*."""
    client = AsyncMock()
    client.connect = AsyncMock()
    client.get_me = AsyncMock(
        return_value=MagicMock(id=user_id)
    )
    client.disconnect = AsyncMock()
    return client


@pytest.mark.asyncio
async def test_live_probe_rejects_dead_session() -> None:
    with tempfile.TemporaryDirectory() as tmp_dir:
        tmp_path = Path(tmp_dir)
        sess_file = tmp_path / "acc.session"
        _create_telethon_session(sess_file)

        with patch("telethon.TelegramClient", return_value=_dead_session_client()):
            probe = await _live_session_probe(sess_file, [(111, "hash")])

        assert probe.authorized is False
        assert probe.user_id is None
        assert probe.reason == "AuthKeyUnregisteredError"
        assert live_failure_label(probe.reason) == "revoked"


@pytest.mark.asyncio
async def test_live_probe_network_error_reported_as_connection_error() -> None:
    with tempfile.TemporaryDirectory() as tmp_dir:
        tmp_path = Path(tmp_dir)
        sess_file = tmp_path / "acc.session"
        _create_telethon_session(sess_file)

        client = AsyncMock()
        client.connect = AsyncMock(side_effect=OSError("network down"))
        client.disconnect = AsyncMock()
        client.get_me = AsyncMock()

        with (
            patch("telethon.TelegramClient", return_value=client),
            patch(
                "app.services.session_to_tdata._probe_connect",
                side_effect=OSError("network down"),
            ),
        ):
            probe = await _live_session_probe(sess_file, [(111, "hash")])

        assert probe.authorized is False
        assert probe.reason == "connection_error"


@pytest.mark.asyncio
async def test_live_probe_retries_transient_error_and_succeeds() -> None:
    """A one-off transient failure must NOT mark a healthy session dead."""
    with tempfile.TemporaryDirectory() as tmp_dir:
        tmp_path = Path(tmp_dir)
        sess_file = tmp_path / "acc.session"
        _create_telethon_session(sess_file)

        client = AsyncMock()
        client.connect = AsyncMock()
        me = MagicMock(id=31337)
        client.get_me = AsyncMock(side_effect=[OSError("blip"), me])
        client.disconnect = AsyncMock()

        with patch("telethon.TelegramClient", return_value=client):
            probe = await _live_session_probe(sess_file, [(111, "hash")])

        assert probe.authorized is True
        assert probe.user_id == 31337


@pytest.mark.asyncio
async def test_convert_live_verification_rejects_dead_session() -> None:
    with tempfile.TemporaryDirectory() as tmp_dir:
        tmp_path = Path(tmp_dir)
        sess_file = tmp_path / "acc.session"
        _create_telethon_session(sess_file)

        with patch("telethon.TelegramClient", return_value=_dead_session_client()):
            success = await convert_session_to_tdata(
                sess_file, tmp_path / "out", credentials=[(111, "hash")]
            )

        assert success is False


@pytest.mark.asyncio
async def test_convert_live_verification_uses_real_owner_id() -> None:
    with tempfile.TemporaryDirectory() as tmp_dir:
        tmp_path = Path(tmp_dir)
        sess_file = tmp_path / "acc.session"
        # The offline tables contain a wrong identity (e.g. a cached peer).
        _create_telethon_session(sess_file, user_id=555666777)

        real_uid = 42424242
        with patch(
            "telethon.TelegramClient", return_value=_authorized_probe_client(real_uid)
        ):
            success = await convert_session_to_tdata(
                sess_file, tmp_path / "tdata_out", credentials=[(111, "hash")]
            )

        assert success is True
        reloaded = TDesktop(str(tmp_path / "tdata_out"))
        assert reloaded.isLoaded() is True
        assert reloaded.accountsCount > 0
        assert reloaded.accounts[0].UserId == real_uid


@pytest.mark.asyncio
async def test_process_live_gate_reports_failed_entries() -> None:
    with tempfile.TemporaryDirectory() as tmp_dir:
        tmp_path = Path(tmp_dir)
        sess_file = tmp_path / "acc.session"
        _create_telethon_session(sess_file)

        with patch("telethon.TelegramClient", return_value=_dead_session_client()):
            res = await process_session_to_tdata_conversion(
                sess_file, tmp_path / "outbox", credentials=[(111, "hash")]
            )

        assert res.total == 1
        assert res.converted == 0
        assert res.failed == 1
        assert res.output_zip_path is None
        assert len(res.entries) == 1
        assert res.entries[0].ok is False
        assert res.entries[0].reason == "AuthKeyUnregisteredError"


@pytest.mark.asyncio
async def test_process_live_gate_progress_done_reaches_total() -> None:
    with tempfile.TemporaryDirectory() as tmp_dir:
        tmp_path = Path(tmp_dir)
        sess_file = tmp_path / "acc.session"
        _create_telethon_session(sess_file)

        progress = JobProgress()
        with patch(
            "telethon.TelegramClient", return_value=_authorized_probe_client(111)
        ):
            await process_session_to_tdata_conversion(
                sess_file, tmp_path / "outbox", credentials=[(111, "hash")], progress=progress
            )

        assert progress.total == 1
        assert progress.done == 1


def test_inspect_session_dc_fallback_uses_extended_map() -> None:
    with tempfile.TemporaryDirectory() as tmp_dir:
        tmp_path = Path(tmp_dir)
        sess_file = tmp_path / "dc3.session"
        with sqlite3.connect(sess_file) as conn:
            conn.execute("CREATE TABLE version (version integer primary key)")
            conn.execute("INSERT INTO version VALUES (7)")
            conn.execute(
                "CREATE TABLE sessions (dc_id integer primary key, server_address text, port integer, auth_key blob, takeout_id integer)"
            )
            conn.execute(
                "INSERT INTO sessions VALUES (3, '', 443, ?, 0)", (b"\x01" * 256,)
            )
            conn.execute(
                "CREATE TABLE entities (id integer primary key, hash integer, username text, phone text, name text, date integer)"
            )
            conn.execute(
                "INSERT INTO entities VALUES (555, 111, 'u', '123', 'N', 1600000000)"
            )

        inspected = _inspect_session(sess_file)
        assert inspected is not None
        dc_id, _auth_key, _user_id, server_address = inspected
        assert dc_id == 3
        assert server_address == "149.154.175.100"


@pytest.mark.asyncio
async def test_session_to_tdata_localization_all_languages() -> None:
    for lang in LANGUAGES:
        assert lang in SESSION_TO_TDATA_PROMPTS
        assert lang in SESSION_TO_TDATA_MESSAGES
        for key in (
            "done",
            "title",
            "summary",
            "converting",
            "no_valid_sessions",
            "btn_retry",
            "btn_home",
            "caption",
            "cancelled",
            "more",
        ):
            assert key in SESSION_TO_TDATA_MESSAGES[lang]
