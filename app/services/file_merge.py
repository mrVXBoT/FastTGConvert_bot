from __future__ import annotations

import asyncio
import logging
import re
import shutil
import sqlite3
import tempfile
import zipfile
from dataclasses import dataclass
from pathlib import Path
from uuid import uuid4

from app.services.account_to_txt import fetch_account_profile
from app.services.files import UnsafeArchiveError
from app.services.session_to_json import _session_connection, render_session_json
from app.services.session_to_tdata import (
    _ensure_opentele_patched,
    convert_session_to_tdata,
)
from app.services.tdata_to_session import (
    convert_tdata_dir_to_sessions,
    find_tdata_dirs,
)
from app.services.tdata_to_session import (
    extract_zip_tdata_safe as extract_zip_safe,
)

LOGGER = logging.getLogger(__name__)


@dataclass(frozen=True)
class FileMergeAccountEntry:
    identifier: str
    user_id: int | None
    phone: str | None
    success: bool


@dataclass(frozen=True)
class FileMergeResult:
    total: int
    merged: int
    failed: int
    output_path: Path | None = None
    is_zip: bool = True
    entries: tuple[FileMergeAccountEntry, ...] = ()


def extract_account_identifier(
    session_path: Path,
) -> tuple[str, int | None, str | None]:
    """
    Extract (identifier, user_id, phone) from sqlite session file.
    """
    user_id: int | None = None
    phone: str | None = None

    try:
        with sqlite3.connect(f"file:{session_path}?mode=ro", uri=True) as conn:
            conn.row_factory = sqlite3.Row
            tables = [
                r[0]
                for r in conn.execute(
                    "SELECT name FROM sqlite_master WHERE type='table'"
                ).fetchall()
            ]

            if "entities" in tables:
                row = conn.execute(
                    "SELECT id, phone FROM entities WHERE phone IS NOT NULL AND"
                    " phone != '' LIMIT 1"
                ).fetchone()
                if row:
                    ph = str(row["phone"]).strip("+")
                    if ph:
                        phone = ph
                    if row["id"]:
                        user_id = int(row["id"])

                if not user_id:
                    row_id = conn.execute(
                        "SELECT id FROM entities WHERE id IS NOT NULL AND id >"
                        " 0 LIMIT 1"
                    ).fetchone()
                    if row_id and row_id[0]:
                        user_id = int(row_id[0])

            if not user_id and "sessions" in tables:
                cols = [
                    r[1] for r in conn.execute("PRAGMA table_info(sessions)").fetchall()
                ]
                if "user_id" in cols:
                    row = conn.execute(
                        "SELECT user_id FROM sessions WHERE user_id > 0 LIMIT 1"
                    ).fetchone()
                    if row and row[0]:
                        user_id = int(row[0])
    except Exception as exc:  # noqa: BLE001
        LOGGER.debug("Could not read details from %s: %s", session_path, exc)

    stem = session_path.stem
    match = re.search(r"\b(\d{7,15})\b", stem)
    if match:
        found_num = match.group(1)
        if not phone and len(found_num) >= 10:
            phone = found_num
        if not user_id:
            user_id = int(found_num)

    if phone:
        identifier = f"+{phone}"
    elif user_id:
        identifier = f"{user_id}"
    else:
        identifier = stem

    return identifier, user_id, phone


def _is_valid_sqlite_session(path: Path) -> bool:
    if not path.exists() or path.stat().st_size == 0:
        return False
    try:
        with sqlite3.connect(f"file:{path}?mode=ro", uri=True) as conn:
            row = conn.execute("SELECT auth_key FROM sessions LIMIT 1").fetchone()
            auth_key = bytes(row[0]) if row and row[0] is not None else b""
            return len(auth_key) == 256 and any(auth_key)
    except Exception:  # noqa: BLE001
        return False


def _safe_account_name(identifier: str, fallback: str) -> str:
    cleaned = re.sub(r"[^0-9A-Za-z_+.-]+", "_", identifier).strip("._")
    return cleaned or fallback


def _deduplicate_paths(paths: list[Path]) -> list[Path]:
    unique: list[Path] = []
    seen: set[Path] = set()
    for path in paths:
        resolved = path.resolve()
        if resolved not in seen:
            seen.add(resolved)
            unique.append(path)
    return unique


async def inspect_mergeable_sessions(input_path: Path) -> list[Path]:
    """
    Inspect input file (ZIP or session) and return a list of valid .session files.
    Converts any tdata directories into session files during inspection.
    """
    if not input_path.exists() or input_path.stat().st_size == 0:
        return []

    discovered_sessions: list[Path] = []
    suffix = input_path.suffix.lower()

    if suffix == ".session":
        if _is_valid_sqlite_session(input_path):
            return [input_path]
        return []

    if suffix == ".zip":
        with tempfile.TemporaryDirectory(prefix="ftgc_merge_inspect_") as tmp_dir:
            tmp_path = Path(tmp_dir)
            extract_zip_safe(input_path, tmp_path)

            # Scan uploaded sessions before writing converted tdata sessions into
            # a separate work directory. This avoids counting converted files twice.
            for path in sorted(tmp_path.rglob("*.session")):
                if path.is_file() and _is_valid_sqlite_session(path):
                    discovered_sessions.append(path)

            tdata_dirs = find_tdata_dirs(tmp_path)
            converted_dir = tmp_path / "_converted_tdata_sessions"
            converted_dir.mkdir(exist_ok=True)
            for t_dir in tdata_dirs:
                out_sess = await convert_tdata_dir_to_sessions(t_dir, converted_dir)
                discovered_sessions.extend(out_sess)

    return _deduplicate_paths(discovered_sessions)


async def process_file_merge(
    input_path: Path,
    merge_type: str,
    output_dir: Path,
    credentials: list[tuple[int, str]] | None = None,
) -> FileMergeResult:
    """
    Merge sessions into ``merged_all.zip`` or a Session+JSON+Tdata archive.
    """
    if not input_path.exists() or input_path.stat().st_size == 0:
        return FileMergeResult(total=0, merged=0, failed=0, output_path=None)
    if merge_type not in {"multi_type", "session_json_tdata"}:
        raise ValueError("invalid_merge_type")

    _ensure_opentele_patched()

    with tempfile.TemporaryDirectory(prefix="ftgc_merge_work_") as tmp_dir:
        tmp_path = Path(tmp_dir)

        session_files: list[Path] = []
        if input_path.suffix.lower() == ".zip":
            try:
                extract_zip_safe(input_path, tmp_path)
            except UnsafeArchiveError:
                raise
            except Exception as exc:  # noqa: BLE001
                LOGGER.warning("Failed extracting ZIP %s: %s", input_path, exc)
                return FileMergeResult(total=0, merged=0, failed=0, output_path=None)

            uploaded_sessions = [
                path
                for path in sorted(tmp_path.rglob("*.session"))
                if path.is_file() and _is_valid_sqlite_session(path)
            ]
            session_files.extend(uploaded_sessions)

            tdata_dirs = find_tdata_dirs(tmp_path)
            converted_dir = tmp_path / "_converted_tdata_sessions"
            converted_dir.mkdir(exist_ok=True)
            for t_dir in tdata_dirs:
                sess_list = await convert_tdata_dir_to_sessions(t_dir, converted_dir)
                session_files.extend(sess_list)

        elif input_path.suffix.lower() == ".session":
            if _is_valid_sqlite_session(input_path):
                copied = tmp_path / input_path.name
                shutil.copy2(input_path, copied)
                session_files = [copied]

        session_files = _deduplicate_paths(session_files)
        total = len(session_files)
        if total == 0:
            return FileMergeResult(total=0, merged=0, failed=0, output_path=None)

        entries: list[FileMergeAccountEntry] = []
        output_dir.mkdir(parents=True, exist_ok=True)

        if merge_type == "multi_type":
            zip_out = output_dir / f"merged_all_{uuid4().hex[:6]}.zip"
            merged_count = 0
            failed_count = 0

            with zipfile.ZipFile(zip_out, "w", zipfile.ZIP_DEFLATED) as zf:
                used_names: set[str] = set()

                for sess_file in session_files:
                    identifier, uid, phone = extract_account_identifier(sess_file)
                    safe_identifier = _safe_account_name(
                        identifier, f"account_{merged_count + 1}"
                    )
                    arc_name = f"{safe_identifier}.session"
                    if arc_name in used_names:
                        arc_name = f"{safe_identifier}_{uuid4().hex[:4]}.session"
                    used_names.add(arc_name)

                    zf.write(sess_file, arcname=arc_name)
                    merged_count += 1
                    entries.append(
                        FileMergeAccountEntry(
                            identifier=identifier,
                            user_id=uid,
                            phone=phone,
                            success=True,
                        )
                    )

            return FileMergeResult(
                total=total,
                merged=merged_count,
                failed=failed_count,
                output_path=zip_out,
                is_zip=True,
                entries=tuple(entries),
            )

        if merge_type == "session_json_tdata":
            zip_out = output_dir / f"merge_json_tdata_{uuid4().hex[:6]}.zip"
            successful: list[tuple[Path, str, str, Path]] = []
            used_clean_ids: set[str] = set()

            # Each session needs a live probe (network) before conversion.
            # Sequential probing made large merges take minutes; a bounded
            # semaphore + indexed gather keeps order while cutting wall time.
            # The probe is done ONCE here; convert_session_to_tdata is called
            # without credentials so it does not re-probe the same session.
            merge_semaphore = asyncio.Semaphore(min(8, total or 1))

            async def merge_one(
                idx: int,
            ) -> tuple[
                int, FileMergeAccountEntry, str | None, tuple[Path, str, str, Path] | None
            ]:
                sess_file = session_files[idx - 1]
                identifier, uid, phone = extract_account_identifier(sess_file)
                async with merge_semaphore:
                    connection = _session_connection(sess_file)
                    status, profile, _reason = await fetch_account_profile(
                        sess_file, credentials or []
                    )
                    if connection is None or profile is None or status == "failed":
                        return idx, FileMergeAccountEntry(identifier, uid, phone, False), None, None

                    display_identifier = (
                        profile.phone if profile.phone != "N/A" else profile.identifier
                    )
                    clean_id = _safe_account_name(
                        profile.identifier.removeprefix("+"), f"account_{idx}"
                    )

                    tdata_temp_dir = tmp_path / f"tdata_out_{idx}"
                    tdata_created = await convert_session_to_tdata(
                        sess_file, tdata_temp_dir
                    )
                    if not tdata_created or not (tdata_temp_dir / "key_datas").is_file():
                        return idx, FileMergeAccountEntry(identifier, uid, phone, False), clean_id, None

                    dc_id, server_address = connection
                    json_content = render_session_json(
                        profile,
                        dc_id=dc_id,
                        server_address=server_address,
                        authorized=status == "active",
                    )
                    conv = (sess_file, clean_id, json_content, tdata_temp_dir)
                    entry = FileMergeAccountEntry(
                        display_identifier,
                        profile.user_id,
                        profile.phone.removeprefix("+")
                        if profile.phone != "N/A"
                        else None,
                        True,
                    )
                    return idx, entry, clean_id, conv

            merge_results = await asyncio.gather(
                *(merge_one(idx) for idx in range(1, total + 1))
            )
            for idx, entry, clean_id, conv in sorted(
                merge_results, key=lambda item: item[0]
            ):
                if clean_id is not None and clean_id in used_clean_ids:
                    clean_id = f"{clean_id}_{idx}"
                if clean_id is not None:
                    used_clean_ids.add(clean_id)
                entries.append(entry)
                if conv is not None and clean_id is not None:
                    sess_file, _, json_content, tdata_dir = conv
                    successful.append((sess_file, clean_id, json_content, tdata_dir))

            success_count = len(successful)
            failed_count = total - success_count
            if success_count == 0:
                return FileMergeResult(
                    total=total,
                    merged=0,
                    failed=failed_count,
                    output_path=None,
                    entries=tuple(entries),
                )

            with zipfile.ZipFile(zip_out, "w", zipfile.ZIP_DEFLATED) as zf:
                multiple = success_count > 1
                for sess_file, clean_id, json_content, tdata_dir in successful:
                    prefix = f"{clean_id}/" if multiple else ""
                    zf.write(sess_file, arcname=f"{prefix}{clean_id}.session")
                    zf.writestr(f"{prefix}{clean_id}.json", json_content)
                    for td_file in sorted(tdata_dir.rglob("*")):
                        if td_file.is_file():
                            rel = td_file.relative_to(tdata_dir)
                            zf.write(td_file, arcname=f"{prefix}tdata/{rel}")

            return FileMergeResult(
                total=total,
                merged=success_count,
                failed=failed_count,
                output_path=zip_out,
                is_zip=True,
                entries=tuple(entries),
            )

        return FileMergeResult(total=total, merged=0, failed=total, output_path=None)
