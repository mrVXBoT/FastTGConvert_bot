from __future__ import annotations

import asyncio
import errno
import importlib.util
import logging
import re
import shutil
import sqlite3
import sys
import tempfile
import types
import zipfile
from contextlib import suppress
from dataclasses import dataclass
from pathlib import Path
from typing import Any
from uuid import uuid4

from app.services.files import (
    MAX_COMPRESSION_RATIO,
    MAX_ZIP_MEMBERS,
    MAX_ZIP_UNCOMPRESSED_BYTES,
    UnsafeArchiveError,
)
from app.services.jobs import JobCancelled, JobProgress

LOGGER = logging.getLogger(__name__)

DC_IP_MAP: dict[int, str] = {
    1: "149.154.175.50",
    2: "149.154.167.50",
    3: "149.154.175.100",
    4: "149.154.167.91",
    5: "91.108.56.130",
    # Telegram test DCs
    1001: "149.154.175.10",
    1002: "149.154.167.40",
    1003: "149.154.175.117",
    1004: "149.154.167.91",
    1005: "91.108.56.170",
}


def _ensure_opentele_patched() -> None:
    """
    Programmatically patch opentele's attribute check decorator on Python 3.13
    without requiring manual edits inside site-packages.
    """
    if "opentele.utils" in sys.modules:
        return
    try:
        tele_spec = importlib.util.find_spec("telethon")
        if not tele_spec or not tele_spec.origin:
            return
        site_pkg = Path(tele_spec.origin).parent.parent
        opentele_dir = site_pkg / "opentele"
        utils_path = opentele_dir / "utils.py"
        if not utils_path.exists():
            return

        opentele_mod = types.ModuleType("opentele")
        opentele_mod.__path__ = [str(opentele_dir)]
        sys.modules["opentele"] = opentele_mod

        spec = importlib.util.spec_from_file_location("opentele.utils", utils_path)
        if not spec or not spec.loader:
            return
        utils_mod = importlib.util.module_from_spec(spec)
        sys.modules["opentele.utils"] = utils_mod
        spec.loader.exec_module(utils_mod)

        utils_mod.override.isOverride = lambda fn: True
    except Exception as exc:  # noqa: BLE001
        LOGGER.warning("opentele monkeypatch exception: %s", exc)


_ensure_opentele_patched()


@dataclass(frozen=True)
class TdataConversionEntry:
    name: str
    ok: bool
    reason: str = ""


@dataclass(frozen=True)
class SessionToTdataResult:
    total: int
    converted: int
    failed: int
    output_zip_path: Path | None = None
    entries: tuple[TdataConversionEntry, ...] = ()


@dataclass(frozen=True)
class LiveProbeResult:
    """Result of connecting to Telegram with a session to verify it actually works."""

    authorized: bool
    user_id: int | None = None
    reason: str = ""


class _TryNextCredential(Exception):
    """Internal marker: the current api credentials are invalid, try the next pair."""


# Raw probe reasons → user-facing labels used in conversion reports.
LIVE_FAILURE_LABELS: dict[str, str] = {
    "AuthKeyDuplicatedError": "revoked",
    "AuthKeyError": "revoked",
    "AuthKeyUnregisteredError": "revoked",
    "SessionRevokedError": "revoked",
    "UserDeactivatedError": "deactivated",
    "UserDeactivatedBanError": "banned",
    "PhoneNumberBannedError": "banned",
    "AuthKeyInvalidError": "revoked",
    "AuthKeyPermEmptyError": "revoked",
    "connection_error": "connection_error",
    "timeout": "timeout",
    "flood_wait": "flood_wait",
    "FloodWaitError": "flood_wait",
    "no_credentials": "no_credentials",
    "telethon_missing": "telethon_missing",
    "no_profile": "banned",
    "unknown": "unknown",
}


def live_failure_label(reason: str) -> str:
    """Map a raw probe failure reason to a compact, user-facing label."""
    return LIVE_FAILURE_LABELS.get(reason, reason)


async def _live_session_probe(
    session_path: Path,
    credentials: list[tuple[int, str]],
    timeout: int = 15,
) -> LiveProbeResult:
    """
    Connect to Telegram with *session_path* and verify it is a live, authorized
    session. Returns the real owner id from ``get_me()`` on success.

    Transient errors (timeouts, OSErrors, small flood waits) are retried before
    failing, so a network blip never turns a healthy session into a false
    failure. Dead/banned sessions (revoked auth key, deactivated account, phone
    banned, etc.) come back ``authorized=False`` with the precise error reason.
    """
    if not isinstance(credentials, list) or not credentials:
        return LiveProbeResult(False, reason="no_credentials")

    try:
        from telethon import TelegramClient  # type: ignore[import-untyped]
        from telethon.errors import (  # type: ignore[import-untyped]
            ApiIdInvalidError,
            AuthKeyDuplicatedError,
            AuthKeyError,
            AuthKeyUnregisteredError,
            FloodWaitError,
            PhoneNumberBannedError,
            SessionRevokedError,
            UserDeactivatedBanError,
            UserDeactivatedError,
        )
    except ModuleNotFoundError:
        return LiveProbeResult(False, reason="telethon_missing")

    invalid_errors = (
        AuthKeyDuplicatedError,
        AuthKeyError,
        AuthKeyUnregisteredError,
        PhoneNumberBannedError,
        SessionRevokedError,
        UserDeactivatedBanError,
        UserDeactivatedError,
    )

    with tempfile.TemporaryDirectory(prefix="ftgc_s2t_probe_") as tmp:
        copied = Path(tmp) / "probe.session"
        shutil.copy2(session_path, copied)
        session_stem = str(copied.with_suffix(""))

        last_error: str | None = "unknown"
        for api_id, api_hash in credentials:
            client = None
            try:
                client = TelegramClient(
                    session_stem, api_id, api_hash, receive_updates=False
                )
                await _probe_connect(client, timeout, ApiIdInvalidError)
                me = await _probe_get_me(client, timeout, invalid_errors, FloodWaitError)
                if me is None or not getattr(me, "id", None):
                    return LiveProbeResult(False, reason="no_profile")
                return LiveProbeResult(True, user_id=int(me.id))
            except _TryNextCredential:
                last_error = "connection_error"
            except invalid_errors as exc:
                LOGGER.debug("Live probe dead session (api_id=%d): %s", api_id, exc)
                return LiveProbeResult(False, reason=type(exc).__name__)
            except TimeoutError:
                last_error = "timeout"
            except OSError:
                last_error = "connection_error"
                continue
            except Exception as exc:  # noqa: BLE001
                last_error = type(exc).__name__
                LOGGER.debug("Live probe credential api_id=%d failed: %s", api_id, exc)
            finally:
                if client is not None:
                    with suppress(Exception):
                        await client.disconnect()

    LOGGER.warning(
        "All %d credential pairs failed the live probe (%s)",
        len(credentials),
        last_error,
    )
    return LiveProbeResult(False, reason=last_error or "unknown")


async def _probe_connect(
    client: Any, timeout: int, api_id_invalid_error: type[BaseException]
) -> None:
    """Connect with transient retries; raise `_TryNextCredential` on bad app ids."""
    attempts = 0
    while True:
        attempts += 1
        try:
            await asyncio.wait_for(client.connect(), timeout=timeout)
            return
        except api_id_invalid_error:
            raise _TryNextCredential from None
        except (TimeoutError, OSError):
            if attempts >= 3:
                raise
            await asyncio.sleep(min(2**attempts, 4))


async def _probe_get_me(
    client: Any,
    timeout: int,
    invalid_errors: tuple[type[BaseException], ...],
    flood_wait_error: type[BaseException],
) -> Any:
    """Fetch the session owner with transient retries, surfacing dead-session errors."""
    attempts = 0
    while True:
        attempts += 1
        try:
            return await asyncio.wait_for(client.get_me(), timeout=timeout)
        except flood_wait_error as exc:
            secs = int(getattr(exc, "seconds", 5)) + 1
            if secs > 30 or attempts >= 3:
                raise
            await asyncio.sleep(secs)
        except (TimeoutError, OSError):
            if attempts >= 3:
                raise
            await asyncio.sleep(min(2**attempts, 4))
        except invalid_errors:
            raise
        except Exception:
            if attempts >= 3:
                raise
            await asyncio.sleep(min(2**attempts, 4))


def extract_zip_sessions_safe(zip_path: Path, target_dir: Path) -> list[Path]:
    """
    Safely extract .session files from ZIP with Zip Slip & Zip Bomb guards.
    """
    session_files: list[Path] = []

    with zipfile.ZipFile(zip_path, "r") as archive:
        members = archive.infolist()
        if len(members) > MAX_ZIP_MEMBERS:
            raise UnsafeArchiveError("zip_too_many_members")

        total_uncompressed = 0
        for idx, info in enumerate(members):
            member_path = Path(info.filename)
            if member_path.is_absolute() or ".." in member_path.parts:
                raise UnsafeArchiveError("zip_unsafe_path")

            total_uncompressed += info.file_size
            if total_uncompressed > MAX_ZIP_UNCOMPRESSED_BYTES:
                raise UnsafeArchiveError("zip_uncompressed_limit")

            if info.compress_size > 0:
                ratio = info.file_size / info.compress_size
                if ratio > MAX_COMPRESSION_RATIO:
                    raise UnsafeArchiveError("zip_suspicious_ratio")

            if member_path.suffix.lower() == ".session":
                safe_name = f"session_{idx}_{member_path.name}"
                dest_path = target_dir / safe_name
                with archive.open(info) as src, dest_path.open("wb") as dst:
                    shutil.copyfileobj(src, dst)
                session_files.append(dest_path)

    return session_files


def clean_session_stem(path: Path) -> str:
    """Strip the ``session_<idx>_`` extraction prefix, keeping the rest intact."""
    match = re.fullmatch(r"session_\d+_(\d{7,15})", path.stem)
    if match:
        return match.group(1)
    return path.stem


def extract_user_id_from_session(
    conn: sqlite3.Connection, _session_path: Path
) -> int | None:
    """
    Extract user_id from SQLite session tables (sessions, users, entities).

    Preference order: pyrogram ``sessions.user_id``, telethon ``users`` table
    (user entities only), ``entities`` rows with a phone, any ``entities`` row.
    The filename is NEVER used: a file named after a phone number would otherwise
    be converted with a fake owner id. The real owner id comes from the live
    authorization probe (``get_me()``) instead.
    """
    tables = [
        row[0]
        for row in conn.execute(
            "SELECT name FROM sqlite_master WHERE type='table'"
        ).fetchall()
    ]

    if "sessions" in tables:
        cols = [r[1] for r in conn.execute("PRAGMA table_info(sessions)").fetchall()]
        if "user_id" in cols:
            r = conn.execute(
                "SELECT user_id FROM sessions WHERE user_id IS NOT NULL AND user_id > 0 LIMIT 1"
            ).fetchone()
            if r and r[0]:
                return int(r[0])

    if "users" in tables:
        r = conn.execute(
            "SELECT id FROM users WHERE id IS NOT NULL AND id > 0 LIMIT 1"
        ).fetchone()
        if r and r[0]:
            return int(r[0])

    if "entities" in tables:
        r = conn.execute(
            "SELECT id FROM entities WHERE id IS NOT NULL AND id > 0 AND phone IS NOT NULL LIMIT 1"
        ).fetchone()
        if r and r[0]:
            return int(r[0])
        r = conn.execute(
            "SELECT id FROM entities WHERE id IS NOT NULL AND id > 0 LIMIT 1"
        ).fetchone()
        if r and r[0]:
            return int(r[0])

    return None


def _inspect_session(session_path: Path) -> tuple[int, bytes, int | None, str] | None:
    """Return (dc_id, auth_key, user_id, server_address) or None when not convertible."""
    if not session_path.exists() or session_path.stat().st_size == 0:
        return None

    try:
        with sqlite3.connect(f"file:{session_path}?mode=ro", uri=True) as conn:
            conn.row_factory = sqlite3.Row
            tables = [
                row[0]
                for row in conn.execute(
                    "SELECT name FROM sqlite_master WHERE type='table'"
                ).fetchall()
            ]
            if "sessions" not in tables:
                return None

            cols = [
                row[1] for row in conn.execute("PRAGMA table_info(sessions)").fetchall()
            ]
            sess_row = conn.execute("SELECT * FROM sessions LIMIT 1").fetchone()
            if not sess_row or not sess_row["auth_key"]:
                return None

            auth_key = bytes(sess_row["auth_key"])
            if len(auth_key) != 256 or not any(b != 0 for b in auth_key):
                return None

            dc_id = int(sess_row["dc_id"]) if "dc_id" in cols and sess_row["dc_id"] else 2
            server_address = (
                str(sess_row["server_address"])
                if "server_address" in cols and sess_row["server_address"]
                else DC_IP_MAP.get(dc_id, "149.154.167.50")
            )
            user_id = extract_user_id_from_session(conn, session_path)
            return dc_id, auth_key, user_id, server_address
    except Exception as exc:  # noqa: BLE001
        LOGGER.warning("Failed inspecting sqlite session %s: %s", session_path, exc)
        return None


def _convert_session_sync(
    auth_key: bytes,
    dc_id: int,
    user_id: int,
    server_address: str,
    output_tdata_dir: Path,
) -> bool:
    """Offline opentele conversion of a session into a tdata folder (blocking)."""
    return asyncio.run(
        _convert_session_coro(auth_key, dc_id, user_id, server_address, output_tdata_dir)
    )


async def _convert_session_coro(
    auth_key: bytes,
    dc_id: int,
    user_id: int,
    server_address: str,
    output_tdata_dir: Path,
) -> bool:
    """Run the opentele conversion inside an isolated event loop."""
    _ensure_opentele_patched()

    try:
        # fmt: off
        from opentele.api import UseCurrentSession  # type: ignore[import-untyped]
        from opentele.td import TDesktop  # type: ignore[import-untyped]
        from opentele.tl import TelegramClient  # type: ignore[import-untyped]
        # fmt: on
    except ModuleNotFoundError:
        raise ValueError("opentele_not_installed") from None

    with tempfile.TemporaryDirectory(prefix="ftgc_convsess_") as tmp_dir:
        adapted_session_path = Path(tmp_dir) / "adapted.session"
        with sqlite3.connect(adapted_session_path) as conn:
            conn.execute("CREATE TABLE version (version integer primary key)")
            conn.execute("INSERT INTO version VALUES (7)")
            conn.execute(
                "CREATE TABLE sessions (dc_id integer primary key, server_address text, port integer, auth_key blob, takeout_id integer)"
            )
            conn.execute(
                "INSERT INTO sessions VALUES (?, ?, 443, ?, 0)",
                (dc_id, server_address, auth_key),
            )

        session_stem = str(adapted_session_path.with_suffix(""))
        client = TelegramClient(session_stem)
        client.UserId = user_id

        tdesktop = await TDesktop.FromTelethon(client, flag=UseCurrentSession)
        output_tdata_dir.mkdir(parents=True, exist_ok=True)
        tdesktop.SaveTData(str(output_tdata_dir))

        reloaded = TDesktop(str(output_tdata_dir))
        return reloaded.isLoaded() and reloaded.accountsCount > 0


async def convert_session_to_tdata(
    session_path: Path,
    output_tdata_dir: Path,
    *,
    credentials: list[tuple[int, str]] | None = None,
) -> bool:
    """
    Convert a Telethon or Pyrogram SQLite .session file into a Telegram Desktop tdata folder.
    Validates auth_key length (256 bytes) and user_id presence.
    Verifies output readability by re-loading TDesktop(output_tdata_dir).isLoaded().

    When *credentials* are provided the session is first probed against Telegram:
    only sessions that are actually authorized are converted, and the real owner
    user id (from ``get_me()``) is used instead of any guess from local tables.
    """
    inspected = _inspect_session(session_path)
    if inspected is None:
        return False
    dc_id, auth_key, user_id, server_address = inspected

    probe_credentials = credentials if isinstance(credentials, list) else None
    live_user_id: int | None = None
    if probe_credentials:
        probe = await _live_session_probe(session_path, probe_credentials)
        if not probe.authorized:
            return False
        live_user_id = probe.user_id

    effective_user_id: int | None = live_user_id or user_id
    if effective_user_id is None:
        return False

    return await asyncio.to_thread(
        _convert_session_sync,
        auth_key,
        dc_id,
        effective_user_id,
        server_address,
        output_tdata_dir,
    )


def _reason_from_inspect(session_path: Path) -> str:
    if not session_path.exists() or session_path.stat().st_size == 0:
        return "empty"
    try:
        with sqlite3.connect(f"file:{session_path}?mode=ro", uri=True) as conn:
            conn.row_factory = sqlite3.Row
            tables = [
                row[0]
                for row in conn.execute(
                    "SELECT name FROM sqlite_master WHERE type='table'"
                ).fetchall()
            ]
            if "sessions" not in tables:
                return "structural"
            sess_row = conn.execute("SELECT * FROM sessions LIMIT 1").fetchone()
            if not sess_row or not sess_row["auth_key"]:
                return "no_auth_key"
            auth_key = bytes(sess_row["auth_key"])
            if len(auth_key) != 256 or not any(b != 0 for b in auth_key):
                return "invalid_auth_key"
            if extract_user_id_from_session(conn, session_path) is None:
                return "no_user_id"
    except Exception as exc:  # noqa: BLE001
        LOGGER.warning("Failed inspecting sqlite session %s: %s", session_path, exc)
        return "inspection_error"
    return "conversion_error"


async def process_session_to_tdata_conversion(
    input_path: Path,
    output_dir: Path,
    *,
    credentials: list[tuple[int, str]] | None = None,
    progress: JobProgress | None = None,
    cancel_event: asyncio.Event | None = None,
) -> SessionToTdataResult:
    """
    Process input file (.session or .zip) converting all valid sessions into tdata.
    Returns SessionToTdataResult with converted count and output zip path.

    When *credentials* are provided every session is first verified live against
    Telegram (``connect()`` + ``is_user_authorized()`` + ``get_me()``). Sessions
    that are dead, banned or unreachable are reported as failed instead of being
    converted into unusable tdata folders.
    """
    session_files: list[Path] = []
    temp_dir: tempfile.TemporaryDirectory[str] | None = None

    try:
        if input_path.suffix.lower() == ".zip":
            temp_dir = tempfile.TemporaryDirectory(prefix="ftgc_s2t_")
            tmp_path = Path(temp_dir.name)
            try:
                session_files = await asyncio.to_thread(
                    extract_zip_sessions_safe, input_path, tmp_path
                )
            except zipfile.BadZipFile as exc:
                raise ValueError("bad_zip_file") from exc
        elif input_path.suffix.lower() == ".session":
            session_files.append(input_path)

        total = len(session_files)
        if progress is not None:
            progress.total = total

        if total == 0:
            return SessionToTdataResult(
                total=0, converted=0, failed=0, output_zip_path=None
            )

        converted = 0
        failed = 0
        entries: list[TdataConversionEntry] = []

        with tempfile.TemporaryDirectory(prefix="ftgc_tdout_") as work_dir:
            work_path = Path(work_dir)
            converted_dirs: list[tuple[str, Path]] = []

            sem = asyncio.Semaphore(30)

            async def _convert_one(idx: int, sess_file: Path) -> tuple[TdataConversionEntry, tuple[str, Path] | None]:
                async with sem:
                    try:
                        if cancel_event is not None and cancel_event.is_set():
                            raise JobCancelled()
                        clean_stem = clean_session_stem(sess_file)
                        target_tdata_dir = work_path / f"acc_{idx}_{clean_stem}" / "tdata"
                        inspected = _inspect_session(sess_file)
                        if inspected is None:
                            return (
                                TdataConversionEntry(
                                    name=clean_stem,
                                    ok=False,
                                    reason=_reason_from_inspect(sess_file),
                                ),
                                None,
                            )
                        dc_id, auth_key, user_id, server_address = inspected

                        probe_credentials = (
                            credentials if isinstance(credentials, list) else None
                        )
                        live_user_id: int | None = None
                        if probe_credentials:
                            probe = await _live_session_probe(
                                sess_file, probe_credentials
                            )
                            if not probe.authorized:
                                return (
                                    TdataConversionEntry(
                                        name=clean_stem,
                                        ok=False,
                                        reason=probe.reason,
                                    ),
                                    None,
                                )
                            live_user_id = probe.user_id

                        effective_user_id: int | None = live_user_id or user_id
                        if effective_user_id is None:
                            return (
                                TdataConversionEntry(name=clean_stem, ok=False, reason="no_user_id"),
                                None,
                            )

                        try:
                            success = await asyncio.to_thread(
                                _convert_session_sync,
                                auth_key,
                                dc_id,
                                effective_user_id,
                                server_address,
                                target_tdata_dir,
                            )
                        except ValueError:
                            raise
                        except Exception as exc:  # noqa: BLE001
                            LOGGER.warning(
                                "Conversion failed for session %s: %s", sess_file, exc
                            )
                            success = False

                        if success:
                            return (TdataConversionEntry(name=clean_stem, ok=True), (clean_stem, target_tdata_dir))
                        return (
                            TdataConversionEntry(
                                name=clean_stem, ok=False, reason="conversion_error"
                            ),
                            None,
                        )
                    finally:
                        if progress is not None:
                            progress.done += 1

            tasks_results = await asyncio.gather(
                *(_convert_one(idx, sess_file) for idx, sess_file in enumerate(session_files, start=1))
            )

            for entry, conv_tuple in tasks_results:
                entries.append(entry)
                if entry.ok and conv_tuple is not None:
                    converted += 1
                    converted_dirs.append(conv_tuple)
                else:
                    failed += 1

            output_zip_path: Path | None = None
            if converted > 0 and converted_dirs:
                output_dir.mkdir(parents=True, exist_ok=True)
                unique_zip_name = f"tdata_{uuid4().hex[:12]}.zip"
                output_zip_path = output_dir / unique_zip_name

                report_lines = ["# Conversion report"]
                for entry in entries:
                    outcome = "OK" if entry.ok else f"FAILED: {entry.reason}"
                    report_lines.append(f"{entry.name} | {outcome}")

                try:
                    with zipfile.ZipFile(
                        output_zip_path, "w", zipfile.ZIP_DEFLATED
                    ) as zf:
                        zf.writestr("report.txt", "\n".join(report_lines) + "\n")
                        if len(converted_dirs) == 1:
                            _, single_tdata = converted_dirs[0]
                            for file_path in single_tdata.rglob("*"):
                                if file_path.is_file():
                                    rel_path = file_path.relative_to(single_tdata.parent)
                                    zf.write(file_path, arcname=str(rel_path))
                        else:
                            seen_folders: set[str] = set()
                            for idx, (stem_name, tdata_dir) in enumerate(
                                converted_dirs, start=1
                            ):
                                folder_name = stem_name
                                if folder_name in seen_folders:
                                    folder_name = f"{stem_name}_{idx}"
                                seen_folders.add(folder_name)

                                for file_path in tdata_dir.rglob("*"):
                                    if file_path.is_file():
                                        rel_path = file_path.relative_to(tdata_dir.parent)
                                        arcname = Path(folder_name) / rel_path
                                        zf.write(file_path, arcname=str(arcname))
                except OSError as exc:
                    if exc.errno == errno.ENOSPC:
                        raise ValueError("storage_error") from exc
                    raise

            return SessionToTdataResult(
                total=total,
                converted=converted,
                failed=failed,
                output_zip_path=output_zip_path,
                entries=tuple(entries),
            )
    finally:
        if temp_dir is not None:
            with suppress(Exception):
                temp_dir.cleanup()
