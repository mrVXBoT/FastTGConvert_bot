from __future__ import annotations

import asyncio
import errno
import logging
import shutil
import sqlite3
import tempfile
import zipfile
from dataclasses import dataclass
from pathlib import Path
from uuid import uuid4

from app.services.files import (
    MAX_COMPRESSION_RATIO,
    MAX_ZIP_MEMBERS,
    MAX_ZIP_UNCOMPRESSED_BYTES,
    UnsafeArchiveError,
)
from app.services.jobs import JobCancelled, JobProgress
from app.services.session_to_tdata import (
    DC_IP_MAP,
    _ensure_opentele_patched,
    _live_session_probe,
)

LOGGER = logging.getLogger(__name__)


@dataclass(frozen=True)
class TdataSessionEntry:
    name: str
    ok: bool
    reason: str = ""


@dataclass(frozen=True)
class TdataToSessionResult:
    total: int
    converted: int
    failed: int
    output_path: Path | None = None
    is_zip: bool = False
    entries: tuple[TdataSessionEntry, ...] = ()


def extract_zip_tdata_safe(zip_path: Path, target_dir: Path) -> None:
    """
    Safely extract files from a ZIP archive containing tdata folders with Zip Slip & Zip Bomb guards.
    """
    try:
        with zipfile.ZipFile(zip_path, "r") as archive:
            members = archive.infolist()
            if len(members) > MAX_ZIP_MEMBERS:
                raise UnsafeArchiveError("zip_too_many_members")

            total_uncompressed = 0
            for info in members:
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

                archive.extract(info, path=target_dir)
    except zipfile.BadZipFile as exc:
        raise ValueError("bad_zip_file") from exc


def find_tdata_dirs(base_dir: Path) -> list[Path]:
    """
    Locate all valid tdata directories containing key_datas/key_data or a D877F783D5* directory.
    """
    tdata_dirs: set[Path] = set()

    for p in base_dir.rglob("*"):
        if (
            p.is_file()
            and p.name.lower() in ("key_datas", "key_data")
            or p.is_dir()
            and p.name.upper().startswith("D877F783D5")
        ):
            tdata_dirs.add(p.parent)

    return sorted(tdata_dirs)


def _convert_tdata_dir_sync(tdata_dir: Path, output_dir: Path) -> list[Path]:
    """Convert a single tdata directory into Telethon .session files (blocking)."""
    _ensure_opentele_patched()

    try:
        from opentele.td import TDesktop  # type: ignore[import-untyped]
    except ModuleNotFoundError:
        raise ValueError("opentele_not_installed") from None

    created_sessions: list[Path] = []
    tdesktop = TDesktop(str(tdata_dir))
    if not tdesktop.isLoaded() or tdesktop.accountsCount == 0:
        return []

    for acc in tdesktop.accounts:
        auth_key_obj = getattr(acc, "authKey", None)
        if not auth_key_obj or not getattr(auth_key_obj, "key", None):
            continue

        auth_key = bytes(auth_key_obj.key)
        if len(auth_key) != 256 or not any(b != 0 for b in auth_key):
            continue

        dc_id = int(getattr(auth_key_obj, "dcId", 2) or 2)
        user_id = getattr(acc, "UserId", None)
        if not user_id or not isinstance(user_id, int) or user_id <= 0:
            LOGGER.warning(
                "Skipping tdata account conversion: user_id could not be determined"
            )
            continue

        server_ip = DC_IP_MAP.get(dc_id, "149.154.167.50")
        session_file = output_dir / f"session_{user_id}.session"
        if session_file.exists():
            session_file = (
                output_dir / f"session_{user_id}_{uuid4().hex[:6]}.session"
            )

        with sqlite3.connect(session_file) as conn:
            conn.execute("CREATE TABLE version (version integer primary key)")
            conn.execute("INSERT INTO version VALUES (7)")
            conn.execute(
                "CREATE TABLE sessions (dc_id integer primary key, server_address text, port integer, auth_key blob, takeout_id integer)"
            )
            conn.execute(
                "INSERT INTO sessions VALUES (?, ?, 443, ?, 0)",
                (dc_id, server_ip, auth_key),
            )
            conn.execute(
                "CREATE TABLE entities (id integer primary key, hash integer, username text, phone text, name text, date integer)"
            )
            conn.execute(
                "INSERT INTO entities VALUES (?, 0, NULL, NULL, NULL, 0)",
                (user_id,),
            )
            conn.execute(
                "CREATE TABLE sent_files (md5_digest blob, file_size integer, type integer, id integer, hash integer, primary key(md5_digest, file_size, type))"
            )
            conn.execute(
                "CREATE TABLE update_state (id integer primary key, pts integer, qts integer, date integer, seq integer)"
            )

        if session_file.exists() and session_file.stat().st_size > 0:
            created_sessions.append(session_file)

    return created_sessions


async def convert_tdata_dir_to_sessions(
    tdata_dir: Path, output_dir: Path
) -> list[Path]:
    """
    Convert a single tdata directory into one or more Telethon .session SQLite files.
    """
    return await asyncio.to_thread(_convert_tdata_dir_sync, tdata_dir, output_dir)


async def process_tdata_to_session_conversion(
    input_path: Path,
    output_dir: Path,
    *,
    credentials: list[tuple[int, str]] | None = None,
    progress: JobProgress | None = None,
    cancel_event: asyncio.Event | None = None,
) -> TdataToSessionResult:
    """
    Process input ZIP file containing tdata folder(s) and convert them to .session file(s).
    Returns TdataToSessionResult with total, converted, failed, and output path.

    When *credentials* are provided every produced session is verified live against
    Telegram; sessions that are dead/unusable are dropped from the results and the
    per-account counts (total/converted/failed) stay consistent.
    """
    if not input_path.exists() or input_path.stat().st_size == 0:
        return TdataToSessionResult(total=0, converted=0, failed=0, output_path=None)

    _ensure_opentele_patched()
    try:
        from opentele.td import TDesktop  # type: ignore[import-untyped]
    except ModuleNotFoundError:
        raise ValueError("opentele_not_installed") from None

    with tempfile.TemporaryDirectory(prefix="ftgc_t2s_") as tmp_dir:
        tmp_path = Path(tmp_dir)

        if input_path.suffix.lower() == ".zip":
            await asyncio.to_thread(extract_zip_tdata_safe, input_path, tmp_path)

        tdata_dirs = find_tdata_dirs(tmp_path)
        if not tdata_dirs:
            return TdataToSessionResult(
                total=0, converted=0, failed=0, output_path=None
            )

        LOGGER.info(
            "Starting TData to Session conversion for %d tdata directory(ies)...",
            len(tdata_dirs),
        )

        if progress is not None:
            progress.total = len(tdata_dirs)

        converted_sessions: list[Path] = []
        entries: list[TdataSessionEntry] = []
        total_accounts = 0

        with tempfile.TemporaryDirectory(prefix="ftgc_t2sout_") as work_dir:
            work_path = Path(work_dir)

            sem = asyncio.Semaphore(30)

            async def _convert_tdata_one(t_dir: Path) -> tuple[TdataSessionEntry, list[Path], int]:
                async with sem:
                    try:
                        if cancel_event is not None and cancel_event.is_set():
                            raise JobCancelled()
                        # Expected accounts for this directory: a discovered tdata
                        # dir implies at least one intended account, so unloadable
                        # dirs count as failures instead of silently vanishing.
                        try:
                            td = TDesktop(str(t_dir))
                            expected = td.accountsCount if td.isLoaded() else 0
                        except Exception as exc:  # noqa: BLE001
                            LOGGER.debug(
                                "Could not pre-count accounts for %s: %s", t_dir, exc
                            )
                            expected = 0
                        if expected <= 0:
                            expected = 1

                        try:
                            sess_list = await convert_tdata_dir_to_sessions(
                                t_dir, work_path
                            )
                        except ValueError:
                            raise
                        except Exception as exc:  # noqa: BLE001
                            LOGGER.warning("Failed converting tdata %s: %s", t_dir, exc)
                            sess_list = []

                        reason = "conversion_error"
                        probe_credentials = (
                            credentials if isinstance(credentials, list) else None
                        )
                        if probe_credentials and sess_list:
                            verified: list[Path] = []
                            for s_file in sess_list:
                                probe = await _live_session_probe(
                                    s_file, probe_credentials
                                )
                                if probe.authorized:
                                    verified.append(s_file)
                                else:
                                    LOGGER.debug(
                                        "Live verification rejected %s: %s",
                                        s_file.name,
                                        probe.reason,
                                    )
                                    reason = probe.reason or "unauthorized"
                            sess_list = verified
                        elif sess_list:
                            reason = ""

                        entry = TdataSessionEntry(
                            name=t_dir.parent.name or t_dir.name,
                            ok=len(sess_list) > 0,
                            reason=reason,
                        )
                        return entry, sess_list, expected
                    finally:
                        if progress is not None:
                            progress.done += 1

            tdata_results = await asyncio.gather(
                *(_convert_tdata_one(t_dir) for t_dir in tdata_dirs)
            )
            for entry, sess_list, expected in tdata_results:
                total_accounts += expected
                entries.append(entry)
                converted_sessions.extend(sess_list)
                if entry.ok:
                    LOGGER.info(
                        "TData -> Session: Folder=%s | Sessions Created=%d → OK",
                        entry.name,
                        len(sess_list),
                    )
                else:
                    LOGGER.warning(
                        "TData -> Session: Folder=%s → FAILED (%s)",
                        entry.name,
                        entry.reason or "conversion_error",
                    )

            converted_count = len(converted_sessions)
            failed_count = total_accounts - converted_count

            if converted_count == 0:
                return TdataToSessionResult(
                    total=total_accounts,
                    converted=0,
                    failed=total_accounts,
                    output_path=None,
                    entries=tuple(entries),
                )

            output_dir.mkdir(parents=True, exist_ok=True)

            if converted_count == 1:
                single_sess = converted_sessions[0]
                out_file = output_dir / single_sess.name
                if out_file.exists():
                    out_file = output_dir / f"converted_{uuid4().hex[:6]}.session"
                shutil.copy2(single_sess, out_file)
                return TdataToSessionResult(
                    total=total_accounts,
                    converted=1,
                    failed=failed_count,
                    output_path=out_file,
                    is_zip=False,
                    entries=tuple(entries),
                )

            zip_out = output_dir / f"sessions_{uuid4().hex[:8]}.zip"
            report_lines = ["# Conversion report"]
            for entry in entries:
                outcome = "OK" if entry.ok else f"FAILED: {entry.reason}"
                report_lines.append(f"{entry.name} | {outcome}")
            try:
                with zipfile.ZipFile(zip_out, "w", zipfile.ZIP_DEFLATED) as zf:
                    zf.writestr("report.txt", "\n".join(report_lines) + "\n")
                    for s_file in converted_sessions:
                        zf.write(s_file, arcname=s_file.name)
            except OSError as exc:
                if exc.errno == errno.ENOSPC:
                    raise ValueError("storage_error") from exc
                raise

            LOGGER.info(
                "TData to Session conversion completed: %d total accounts, %d converted, %d failed.",
                total_accounts,
                converted_count,
                failed_count,
            )
            return TdataToSessionResult(
                total=total_accounts,
                converted=converted_count,
                failed=failed_count,
                output_path=zip_out,
                is_zip=True,
                entries=tuple(entries),
            )
