from __future__ import annotations

import json
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

DC_IP_MAP = {
    1: "149.154.175.50",
    2: "149.154.167.50",
    3: "149.154.175.100",
    4: "149.154.167.91",
    5: "91.108.56.130",
}


@dataclass(frozen=True)
class SessionJsonEntry:
    profile: AccountProfile
    authorized: bool

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
        return self.active + self.invalid_converted


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
    }
    return json.dumps(payload, ensure_ascii=False, indent=2) + "\n"


async def process_session_to_json(
    input_path: Path,
    output_dir: Path,
    credentials: list[tuple[int, str]],
    *,
    original_name: str | None = None,
) -> SessionJsonResult:
    temp_dir: tempfile.TemporaryDirectory[str] | None = None
    session_files: list[Path] = []

    try:
        suffix = Path(original_name or input_path.name).suffix.lower()
        if suffix == ".zip":
            temp_dir = tempfile.TemporaryDirectory(prefix="ftgc_session_json_zip_")
            session_files = extract_zip_sessions_safe(input_path, Path(temp_dir.name))
        elif suffix == ".session":
            if original_name:
                temp_dir = tempfile.TemporaryDirectory(prefix="ftgc_session_json_one_")
                copied = Path(temp_dir.name) / Path(original_name).name
                shutil.copy2(input_path, copied)
                session_files = [copied]
            else:
                session_files = [input_path]

        active = 0
        invalid_converted = 0
        failed = 0
        outputs: list[tuple[str, str]] = []
        entries: list[SessionJsonEntry] = []

        for session_file in session_files:
            if not _is_structural_session(session_file):
                failed += 1
                continue
            connection = _session_connection(session_file)
            if connection is None:
                failed += 1
                continue

            status, profile = await fetch_account_profile(session_file, credentials)
            if status == "active" and profile is not None:
                authorized = True
                active += 1
            elif status == "invalid" and profile is not None:
                authorized = False
                invalid_converted += 1
            else:
                failed += 1
                continue

            dc_id, server_address = connection
            entries.append(SessionJsonEntry(profile=profile, authorized=authorized))
            outputs.append(
                (
                    f"{profile.identifier}.json",
                    render_session_json(
                        profile,
                        dc_id=dc_id,
                        server_address=server_address,
                        authorized=authorized,
                    ),
                )
            )

        output_zip: Path | None = None
        if outputs:
            output_dir.mkdir(parents=True, exist_ok=True)
            output_zip = output_dir / f"session_json_{uuid4().hex[:10]}.zip"
            with zipfile.ZipFile(output_zip, "w", zipfile.ZIP_DEFLATED) as archive:
                used: set[str] = set()
                for index, (filename, content) in enumerate(outputs, start=1):
                    arcname = filename
                    if arcname in used:
                        arcname = f"{Path(filename).stem}_{index}.json"
                    used.add(arcname)
                    archive.writestr(arcname, content)

        return SessionJsonResult(
            total=len(session_files),
            active=active,
            invalid_converted=invalid_converted,
            failed=failed,
            entries=tuple(entries),
            output_zip_path=output_zip,
        )
    finally:
        if temp_dir is not None:
            temp_dir.cleanup()
