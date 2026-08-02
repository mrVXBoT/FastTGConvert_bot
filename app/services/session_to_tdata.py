from __future__ import annotations

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
from uuid import uuid4

from app.services.files import (
    MAX_COMPRESSION_RATIO,
    MAX_ZIP_MEMBERS,
    MAX_ZIP_UNCOMPRESSED_BYTES,
    UnsafeArchiveError,
)

LOGGER = logging.getLogger(__name__)

DC_IP_MAP: dict[int, str] = {
    1: "149.154.175.50",
    2: "149.154.167.50",
    3: "149.154.175.100",
    4: "149.154.167.91",
    5: "91.108.56.130",
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
class SessionToTdataResult:
    total: int
    converted: int
    failed: int
    output_zip_path: Path | None = None


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


def extract_user_id_from_session(
    conn: sqlite3.Connection, session_path: Path
) -> int | None:
    """
    Extract user_id from SQLite session tables (sessions, entities, users) or filename.
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

    if "entities" in tables:
        r = conn.execute(
            "SELECT id FROM entities WHERE id IS NOT NULL AND id > 0 LIMIT 1"
        ).fetchone()
        if r and r[0]:
            return int(r[0])

    if "users" in tables:
        r = conn.execute(
            "SELECT id FROM users WHERE id IS NOT NULL AND id > 0 LIMIT 1"
        ).fetchone()
        if r and r[0]:
            return int(r[0])

    match = re.search(r"\b(\d{7,15})\b", session_path.stem)
    if match:
        return int(match.group(1))

    return None


async def convert_session_to_tdata(
    session_path: Path,
    output_tdata_dir: Path,
) -> bool:
    """
    Convert a Telethon or Pyrogram SQLite .session file into a Telegram Desktop tdata folder.
    Validates auth_key length (256 bytes) and user_id presence.
    Verifies output readability by re-loading TDesktop(output_tdata_dir).isLoaded().
    """
    if not session_path.exists() or session_path.stat().st_size == 0:
        return False

    _ensure_opentele_patched()

    try:
        # fmt: off
        from opentele.api import UseCurrentSession  # type: ignore[import-untyped]
        from opentele.td import TDesktop  # type: ignore[import-untyped]
        from opentele.tl import TelegramClient  # type: ignore[import-untyped]
        # fmt: on
    except ModuleNotFoundError:
        LOGGER.error("opentele not installed for session to tdata conversion")
        return False

    dc_id = 2
    auth_key: bytes | None = None
    user_id: int | None = None

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
                return False

            cols = [
                row[1] for row in conn.execute("PRAGMA table_info(sessions)").fetchall()
            ]
            sess_row = conn.execute("SELECT * FROM sessions LIMIT 1").fetchone()
            if not sess_row or not sess_row["auth_key"]:
                return False

            auth_key = bytes(sess_row["auth_key"])
            # Auth key must be 256 bytes for Telegram auth_key specification
            if len(auth_key) != 256 or not any(b != 0 for b in auth_key):
                return False

            if "dc_id" in cols and sess_row["dc_id"]:
                dc_id = int(sess_row["dc_id"])

            user_id = extract_user_id_from_session(conn, session_path)
            if user_id is None:
                # If user_id could not be resolved from DB/filename, conversion is unreliable
                return False

    except Exception as exc:  # noqa: BLE001
        LOGGER.warning("Failed inspecting sqlite session %s: %s", session_path, exc)
        return False

    with tempfile.TemporaryDirectory(prefix="ftgc_convsess_") as tmp_dir:
        adapted_session_path = Path(tmp_dir) / "adapted.session"
        try:
            with sqlite3.connect(adapted_session_path) as conn:
                conn.execute("CREATE TABLE version (version integer primary key)")
                conn.execute("INSERT INTO version VALUES (7)")
                conn.execute(
                    "CREATE TABLE sessions (dc_id integer primary key, server_address text, port integer, auth_key blob, takeout_id integer)"
                )
                server_ip = DC_IP_MAP.get(dc_id, "149.154.167.50")
                conn.execute(
                    "INSERT INTO sessions VALUES (?, ?, 443, ?, 0)",
                    (dc_id, server_ip, auth_key),
                )

            session_stem = str(adapted_session_path.with_suffix(""))
            client = TelegramClient(session_stem)
            client.UserId = user_id

            tdesktop = await TDesktop.FromTelethon(client, flag=UseCurrentSession)
            output_tdata_dir.mkdir(parents=True, exist_ok=True)
            tdesktop.SaveTData(str(output_tdata_dir))

            # Verify readability and validity of created TDesktop data
            reloaded = TDesktop(str(output_tdata_dir))
            return reloaded.isLoaded() and reloaded.accountsCount > 0
        except Exception as exc:  # noqa: BLE001
            LOGGER.warning("Conversion failed for session %s: %s", session_path, exc)
            return False


async def process_session_to_tdata_conversion(
    input_path: Path,
    output_dir: Path,
) -> SessionToTdataResult:
    """
    Process input file (.session or .zip) converting all valid sessions into tdata.
    Returns SessionToTdataResult with converted count and output zip path.
    """
    session_files: list[Path] = []
    temp_dir: tempfile.TemporaryDirectory[str] | None = None

    try:
        if input_path.suffix.lower() == ".zip":
            temp_dir = tempfile.TemporaryDirectory(prefix="ftgc_s2t_")
            tmp_path = Path(temp_dir.name)
            session_files = extract_zip_sessions_safe(input_path, tmp_path)
        elif input_path.suffix.lower() == ".session":
            session_files.append(input_path)

        total = len(session_files)
        converted = 0
        failed = 0

        if total == 0:
            return SessionToTdataResult(
                total=0, converted=0, failed=0, output_zip_path=None
            )

        with tempfile.TemporaryDirectory(prefix="ftgc_tdout_") as work_dir:
            work_path = Path(work_dir)
            converted_dirs: list[tuple[str, Path]] = []

            for idx, sess_file in enumerate(session_files, start=1):
                clean_stem = sess_file.stem
                if clean_stem.startswith("session_"):
                    parts = clean_stem.split("_", 2)
                    if len(parts) >= 3:
                        clean_stem = parts[2]

                target_tdata_dir = work_path / f"acc_{idx}_{clean_stem}" / "tdata"
                success = await convert_session_to_tdata(sess_file, target_tdata_dir)
                if success:
                    converted += 1
                    converted_dirs.append((clean_stem, target_tdata_dir))
                else:
                    failed += 1

            output_zip_path: Path | None = None
            if converted > 0 and converted_dirs:
                output_dir.mkdir(parents=True, exist_ok=True)
                unique_zip_name = f"tdata_{uuid4().hex[:12]}.zip"
                output_zip_path = output_dir / unique_zip_name

                with zipfile.ZipFile(output_zip_path, "w", zipfile.ZIP_DEFLATED) as zf:
                    if len(converted_dirs) == 1:
                        # Single account: store tdata folder at root (tdata/key_datas, etc.)
                        _, single_tdata = converted_dirs[0]
                        for file_path in single_tdata.rglob("*"):
                            if file_path.is_file():
                                rel_path = file_path.relative_to(single_tdata.parent)
                                zf.write(file_path, arcname=str(rel_path))
                    else:
                        # Multiple accounts: store each account folder (account_1_stem/tdata/key_datas, etc.)
                        for idx, (stem_name, tdata_dir) in enumerate(
                            converted_dirs, start=1
                        ):
                            acc_folder_name = f"account_{idx}_{stem_name}"
                            for file_path in tdata_dir.rglob("*"):
                                if file_path.is_file():
                                    rel_path = file_path.relative_to(tdata_dir.parent)
                                    arcname = Path(acc_folder_name) / rel_path
                                    zf.write(file_path, arcname=str(arcname))

            return SessionToTdataResult(
                total=total,
                converted=converted,
                failed=failed,
                output_zip_path=output_zip_path,
            )
    finally:
        if temp_dir is not None:
            with suppress(Exception):
                temp_dir.cleanup()
