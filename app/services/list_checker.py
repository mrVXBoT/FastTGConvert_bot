"""list_checker.py — Robust File Matcher / List Checker service.

Compares two ZIP archives and finds common items by identifier:
  • Tdata folders  — Telegram desktop folders (matched by phone number or folder name)
  • .session files — matched by base name without extension (case-insensitive)
  • .json files    — matched by base name without extension (case-insensitive)

Features & Hardening:
  - Case-insensitive key matching across archives
  - Handles both explicit folder entries and implicit paths without folder headers
  - Zip Slip & path traversal protection
  - Safe handling of corrupted/truncated ZIP files
  - Deduplication and preservation of complete directory structures from Archive 1
"""
from __future__ import annotations

import io
import logging
import os
import struct
import zipfile
from dataclasses import dataclass
from pathlib import Path

LOGGER = logging.getLogger(__name__)


@dataclass(frozen=True)
class ListCheckerResult:
    tdata_count: int
    session_count: int
    json_count: int
    total: int
    output_bytes: bytes | None   # None when total == 0


def _is_safe_path(path: str) -> bool:
    """Return True if path is safe from Zip Slip & path traversal vulnerabilities."""
    normalized = path.replace("\\", "/").strip()
    if not normalized or normalized.startswith("/"):
        return False
    parts = normalized.split("/")
    return ".." not in parts


def _extract_tdata_key(parent_parts: list[str]) -> str | None:
    """Determine the Tdata folder identifier key from parent directory parts.

    Prioritizes numeric/phone folder names (e.g. '596696702021') or 'tdata'.
    Fallback to the first top-level parent folder without a dot extension.
    """
    if not parent_parts:
        return None

    # Check for explicit numeric/phone or 'tdata' folders
    for part in reversed(parent_parts):
        clean = part.strip().lstrip("+")
        if clean.isdigit() and len(clean) >= 5:
            return clean.lower()
        if part.lower() == "tdata":
            idx = parent_parts.index(part)
            if idx > 0 and "." not in parent_parts[idx - 1]:
                return parent_parts[idx - 1].lower()
            return "tdata"

    # Fallback to first parent folder without extension
    for part in parent_parts:
        if "." not in part and part.lower() not in ("files", "emoji", "user_data", "temp"):
            return part.lower()

    return None


def _index_archive(data: bytes) -> tuple[
    dict[str, list[str]],  # tdata_map: key -> [entry_paths]
    dict[str, list[str]],  # session_map: key -> [entry_paths]
    dict[str, list[str]],  # json_map: key -> [entry_paths]
    dict[str, bytes],      # all_files: entry_path -> bytes
]:
    """Parse ZIP bytes and build maps of identifiers to entry paths and file contents."""
    tdata_map: dict[str, list[str]] = {}
    session_map: dict[str, list[str]] = {}
    json_map: dict[str, list[str]] = {}
    all_files: dict[str, bytes] = {}

    try:
        with zipfile.ZipFile(io.BytesIO(data)) as zf:
            for name in zf.namelist():
                norm = name.replace("\\", "/").strip()
                if not _is_safe_path(norm):
                    LOGGER.warning("Skipping unsafe archive path: %r", name)
                    continue

                is_dir = norm.endswith("/")
                parts = norm.rstrip("/").split("/")

                if is_dir:
                    # Explicit directory entry
                    if len(parts) == 1 and "." not in parts[0]:
                        key = parts[0].lower().lstrip("+")
                        tdata_map.setdefault(key, [])
                    elif len(parts) > 1:
                        td_key = _extract_tdata_key(parts)
                        if td_key:
                            tdata_map.setdefault(td_key, [])
                else:
                    # File entry
                    file_bytes = zf.read(name)
                    all_files[norm] = file_bytes
                    filename = parts[-1]
                    ext = os.path.splitext(filename)[1].lower()

                    if ext == ".session":
                        key = os.path.splitext(filename)[0].lower()
                        session_map.setdefault(key, []).append(norm)
                    elif ext == ".json":
                        key = os.path.splitext(filename)[0].lower()
                        json_map.setdefault(key, []).append(norm)
                    else:
                        # Check if file belongs to a Tdata directory
                        parent_parts = parts[:-1]
                        td_key = _extract_tdata_key(parent_parts)
                        if td_key:
                            tdata_map.setdefault(td_key, []).append(norm)

    except (zipfile.BadZipFile, OSError, KeyError, MemoryError, struct.error) as err:
        raise ValueError(f"Corrupted or invalid ZIP archive: {err}") from err

    return tdata_map, session_map, json_map, all_files


def compare_archives(data1: bytes, data2: bytes) -> ListCheckerResult:
    """Compare two ZIP archives and build a output ZIP with matched items from Archive 1.

    Matching is case-insensitive by item identifier.
    Returns ListCheckerResult with counts and output ZIP bytes (or None if no match).
    """
    tdata_map1, session_map1, json_map1, all_files1 = _index_archive(data1)
    tdata_map2, session_map2, json_map2, _ = _index_archive(data2)

    # ── Calculate intersections ───────────────────────────────────────────────
    common_tdata_keys = set(tdata_map1.keys()) & set(tdata_map2.keys())
    common_session_keys = set(session_map1.keys()) & set(session_map2.keys())
    common_json_keys = set(json_map1.keys()) & set(json_map2.keys())

    tdata_count = len(common_tdata_keys)
    session_count = len(common_session_keys)
    json_count = len(common_json_keys)
    total = tdata_count + session_count + json_count

    if total == 0:
        return ListCheckerResult(
            tdata_count=0, session_count=0, json_count=0, total=0, output_bytes=None
        )

    # ── Build result ZIP from Archive 1 contents ──────────────────────────────
    out_buf = io.BytesIO()
    written_entries: set[str] = set()

    with zipfile.ZipFile(out_buf, "w", zipfile.ZIP_DEFLATED) as out_zip:
        # Write matched Tdata folders (preserving original folder structure)
        for key in sorted(common_tdata_keys):
            for file_entry in tdata_map1[key]:
                if file_entry in all_files1 and file_entry not in written_entries:
                    out_zip.writestr(file_entry, all_files1[file_entry])
                    written_entries.add(file_entry)

        # Write matched .session files (flat at root)
        for key in sorted(common_session_keys):
            for entry_path in session_map1[key]:
                if entry_path in all_files1:
                    base_name = os.path.basename(entry_path)
                    if base_name not in written_entries:
                        out_zip.writestr(base_name, all_files1[entry_path])
                        written_entries.add(base_name)

        # Write matched .json files (flat at root)
        for key in sorted(common_json_keys):
            for entry_path in json_map1[key]:
                if entry_path in all_files1:
                    base_name = os.path.basename(entry_path)
                    if base_name not in written_entries:
                        out_zip.writestr(base_name, all_files1[entry_path])
                        written_entries.add(base_name)

    LOGGER.info(
        "ListChecker: tdata=%d sessions=%d json=%d total=%d",
        tdata_count, session_count, json_count, total,
    )
    return ListCheckerResult(
        tdata_count=tdata_count,
        session_count=session_count,
        json_count=json_count,
        total=total,
        output_bytes=out_buf.getvalue(),
    )


def compare_archive_files(path1: Path, path2: Path) -> ListCheckerResult:
    """Load two ZIP files from disk and compare them."""
    data1 = path1.read_bytes()
    data2 = path2.read_bytes()
    return compare_archives(data1, data2)
