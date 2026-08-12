from __future__ import annotations

import asyncio
import errno
import json
import logging
import shutil
import sqlite3
import tempfile
import zipfile
from dataclasses import dataclass
from pathlib import Path
from uuid import uuid4

from app.services.account_to_txt import (
    AccountProfile,
    _is_structural_session,
    fetch_account_profile,
)
from app.services.contacts_checker import extract_zip_sessions_safe
from app.services.jobs import JobCancelled, JobProgress

LOGGER = logging.getLogger(__name__)

DC_IP_MAP = {
    1: "149.154.175.50",
    2: "149.154.167.50",
    3: "149.154.175.100",
    4: "149.154.167.91",
    5: "91.108.56.130",
}

# Max concurrent network probes (see account_to_txt._PROBE_CONCURRENCY).
_PROBE_CONCURRENCY = 8


@dataclass(frozen=True)
class SessionJsonEntry:
    profile: AccountProfile
    authorized: bool
    reason: str = ""

    @property
    def report_icon(self) -> str:
        return "✅" if self.authorized else "⚠️"


@dataclass(frozen=True)
class SessionJsonResult:
    total: int
    active: int
    invalid_converted: int
    failed: int
    entries: tuple[SessionJsonEntry, ...] = ()
    output_zip_path: Path | None = None

    @property
    def converted(self) -> int:
        # Only authorized sessions count as converted. Invalid (banned /
        # deactivated) sessions still get a JSON file under Invalid/ but they
        # are NOT usable accounts, so they must not inflate the count.
        return self.active


def _session_connection(path: Path) -> tuple[int, str] | None:
    try:
        with sqlite3.connect(f"file:{path}?mode=ro", uri=True) as conn:
            conn.row_factory = sqlite3.Row
            columns = {row[1] for row in conn.execute("PRAGMA table_info(sessions)")}
            row = conn.execute("SELECT * FROM sessions LIMIT 1").fetchone()
            if row is None or "dc_id" not in columns:
                return None
            dc_id = int(row["dc_id"])
            server = (
                str(row["server_address"])
                if "server_address" in columns and row["server_address"]
                else DC_IP_MAP.get(dc_id, "149.154.167.50")
            )
            return dc_id, server
    except (sqlite3.DatabaseError, OSError, ValueError):
        return None


def render_session_json(
    profile: AccountProfile,
    *,
    dc_id: int,
    server_address: str,
    authorized: bool,
) -> str:
    payload = {
        "name": profile.identifier,
        "phone": profile.phone,
        "username": profile.username,
        "full_name": profile.full_name,
        "user_id": profile.user_id,
        "premium": profile.premium,
        "dc_id": dc_id,
        "server_address": server_address,
        "authorized": authorized,
        "two_fa": profile.two_fa,
        "registered": profile.registered,
    }
    return json.dumps(payload, ensure_ascii=False, indent=2) + "\n"


async def process_session_to_json(
    input_path: Path,
    output_dir: Path,
    credentials: list[tuple[int, str]],
    *,
    original_name: str | None = None,
    progress: JobProgress | None = None,
    cancel_event: asyncio.Event | None = None,
) -> SessionJsonResult:
    temp_dir: tempfile.TemporaryDirectory[str] | None = None
    session_files: list[Path] = []

    try:
        suffix = Path(original_name or input_path.name).suffix.lower()
        if suffix == ".zip":
            temp_dir = tempfile.TemporaryDirectory(prefix="ftgc_session_json_zip_")
            try:
                session_files = await asyncio.to_thread(
                    extract_zip_sessions_safe, input_path, Path(temp_dir.name)
                )
            except zipfile.BadZipFile as exc:
                raise ValueError("bad_zip_file") from exc
        elif suffix == ".session":
            if original_name:
                temp_dir = tempfile.TemporaryDirectory(prefix="ftgc_session_json_one_")
                copied = Path(temp_dir.name) / Path(original_name).name
                shutil.copy2(input_path, copied)
                session_files = [copied]
            else:
                session_files = [input_path]

        total = len(session_files)
        if progress is not None:
            progress.total = total

        LOGGER.info(
            "Starting Session to JSON conversion for '%s' (%d session(s))...",
            original_name or input_path.name,
            total,
        )

        active = 0
        invalid_converted = 0
        failed = 0
        outputs: list[tuple[str, str, bool]] = []
        entries: list[SessionJsonEntry] = []

        fetch_semaphore = asyncio.Semaphore(
            min(_PROBE_CONCURRENCY, len(session_files) or 1)
        )

        async def probe_session(
            index: int,
        ) -> tuple[int, str, SessionJsonEntry, tuple[str, str, bool] | None]:
            if cancel_event is not None and cancel_event.is_set():
                raise JobCancelled()
            session_file = session_files[index]
            if not _is_structural_session(session_file):
                return (
                    index,
                    "failed",
                    SessionJsonEntry(
                        profile=AccountProfile(
                            identifier=session_file.stem,
                            phone="N/A",
                            username="N/A",
                            full_name="N/A",
                            user_id=0,
                        ),
                        authorized=False,
                        reason="structural",
                    ),
                    None,
                )
            connection = _session_connection(session_file)
            if connection is None:
                return (
                    index,
                    "failed",
                    SessionJsonEntry(
                        profile=AccountProfile(
                            identifier=session_file.stem,
                            phone="N/A",
                            username="N/A",
                            full_name="N/A",
                            user_id=0,
                        ),
                        authorized=False,
                        reason="no_connection",
                    ),
                    None,
                )
            async with fetch_semaphore:
                status, profile, reason = await fetch_account_profile(
                    session_file, credentials
                )
            if status == "active" and profile is not None:
                authorized = True
            elif status == "invalid" and profile is not None:
                authorized = False
            else:
                return (
                    index,
                    "failed",
                    SessionJsonEntry(
                        profile=AccountProfile(
                            identifier=session_file.stem,
                            phone="N/A",
                            username="N/A",
                            full_name="N/A",
                            user_id=0,
                        ),
                        authorized=False,
                        reason=reason,
                    ),
                    None,
                )

            dc_id, server_address = connection
            entry = SessionJsonEntry(
                profile=profile, authorized=authorized, reason=reason
            )
            output = (
                f"{profile.identifier}.json",
                render_session_json(
                    profile,
                    dc_id=dc_id,
                    server_address=server_address,
                    authorized=authorized,
                ),
                authorized,
            )
            return index, status, entry, output

        async def tracked_probe(
            index: int,
        ) -> tuple[int, str, SessionJsonEntry, tuple[str, str, bool] | None]:
            outcome = await probe_session(index)
            if progress is not None:
                progress.done += 1
            return outcome

        outcomes = await asyncio.gather(
            *(tracked_probe(index) for index in range(len(session_files)))
        )
        for index, status, entry, output in sorted(outcomes, key=lambda item: item[0]):
            if status == "active":
                active += 1
                LOGGER.info(
                    "Session -> JSON: Account=%s | Phone=%s | UserID=%s → ACTIVE (OK)",
                    entry.profile.identifier,
                    entry.profile.phone,
                    entry.profile.user_id or "N/A",
                )
            elif status == "invalid":
                invalid_converted += 1
                LOGGER.warning(
                    "Session -> JSON: Account=%s | Phone=%s | UserID=%s → INVALID (%s)",
                    entry.profile.identifier,
                    entry.profile.phone,
                    entry.profile.user_id or "N/A",
                    entry.reason or "invalid",
                )
            else:
                failed += 1
                LOGGER.warning(
                    "Session -> JSON: Account=%s → FAILED (%s)",
                    entry.profile.identifier,
                    entry.reason or "failed",
                )
            entries.append(entry)
            if output is not None:
                outputs.append(output)

        output_zip: Path | None = None
        if outputs:
            output_dir.mkdir(parents=True, exist_ok=True)
            output_zip = output_dir / f"session_json_{uuid4().hex[:10]}.zip"
            try:
                with zipfile.ZipFile(output_zip, "w", zipfile.ZIP_DEFLATED) as archive:
                    used: set[str] = set()
                    for index, (filename, content, authorized) in enumerate(
                        outputs, start=1
                    ):
                        arcname = filename
                        if arcname in used:
                            arcname = f"{Path(filename).stem}_{index}.json"
                        used.add(arcname)
                        if not authorized:
                            arcname = f"Invalid/{arcname}"
                        archive.writestr(arcname, content)
            except OSError as exc:
                if exc.errno == errno.ENOSPC:
                    raise ValueError("storage_error") from exc
                raise

        res = SessionJsonResult(
            total=len(session_files),
            active=active,
            invalid_converted=invalid_converted,
            failed=failed,
            entries=tuple(entries),
            output_zip_path=output_zip,
        )
        LOGGER.info(
            "Session to JSON Summary: Total=%d | Active=%d | Invalid Converted=%d | Failed=%d | Output=%s",
            res.total,
            res.active,
            res.invalid_converted,
            res.failed,
            output_zip.name if output_zip else "None",
        )
        return res
    finally:
        if temp_dir is not None:
            temp_dir.cleanup()
