"""
Two-phase session checker.

Phase 1 – Offline structural check (always runs, no network):
  Inspect the SQLite file to confirm it is a well-formed Telethon / Pyrogram
  session file with a non-empty auth_key.

Phase 2 – Live spam check via @SpamBot (runs only when api_id / api_hash are
  configured):
  Connect with the session and query @SpamBot to determine whether Telegram
  has applied any restrictions to the account.

Result mapping
--------------
+---------------------+---------------------+----------------------------+
| Phase 1             | Phase 2             | SessionCheckResult bucket  |
+=====================+=====================+============================+
| structurally_valid  | active              | active                     |
| structurally_valid  | spam                | spam                       |
| structurally_valid  | frozen              | frozen                     |
| structurally_valid  | banned              | banned                     |
| structurally_valid  | invalid             | invalid                    |
| structurally_valid  | inconclusive        | inconclusive               |
| structurally_valid  | (no credentials)    | inconclusive ← unverified  |
| incomplete          | (skipped)           | frozen (inferred offline   |
|                     |                     |   from a wiped auth key;   |
|                     |                     |   never falsely "active")  |
| invalid             | (skipped)           | invalid                    |
+---------------------+---------------------+----------------------------+

Accepted file extensions: ``.session`` and ``.zip``.
ZIP archives may contain multiple ``.session`` members; each is checked
independently so one failure never aborts the rest.

Security constraints:
  • MAX_ZIP_MEMBERS:            2 000 entries
  • MAX_ZIP_UNCOMPRESSED_BYTES: 512 MiB total
  • Zip Slip prevention (absolute paths / ".." rejected)
  • Max compression ratio: 200× (zip-bomb guard)
  • ZIP members are read in 256 KiB chunks to bound RAM usage.
  • No auth_key, phone number, or session bytes are logged.
"""

from __future__ import annotations

import asyncio
import logging
import re
import sqlite3
import tempfile
import zipfile
from dataclasses import dataclass
from pathlib import Path
from typing import Literal

from app.session_results import SessionCheckResult

__all__ = [
    "SessionCheckEntry",
    "SessionProgress",
    "check_sessions",
    "check_sessions_detailed",
]

LOGGER = logging.getLogger(__name__)

# --------------------------------------------------------------------------- #
# Constants                                                                    #
# --------------------------------------------------------------------------- #

_MAX_ZIP_MEMBERS = 2_000
_MAX_ZIP_UNCOMPRESSED_BYTES = 512 * 1024 * 1024
_MAX_COMPRESSION_RATIO = 200
_CHUNK_SIZE = 256 * 1024  # 256 KiB – read ZIP members in chunks to cap RAM

_ALLOWED_SUFFIXES = {".session", ".zip"}

# Internal labels for what offline inspection can determine.
_OfflineStatus = Literal["structurally_valid", "incomplete", "invalid"]

# Final labels after both phases – mirrors SpamStatus + offline-only labels.
_FinalStatus = Literal["active", "spam", "frozen", "banned", "invalid", "inconclusive"]


@dataclass(frozen=True)
class SessionCheckEntry:
    """
    Per-session check result.

    ``member`` is the original member path inside the uploaded ZIP archive
    (or the bare file name for a single ``.session`` upload); it is what the
    status ZIP separation uses to regroup files by outcome.  Empty for a
    malformed archive where no member could be identified.
    """

    member: str
    status: _FinalStatus
    phone: str | None = None


@dataclass
class SessionProgress:
    """Shared mutable progress state for a running session check."""

    total: int = 0
    done: int = 0


# --------------------------------------------------------------------------- #
# Phase 1 – offline structural check (synchronous, run via asyncio.to_thread) #
# --------------------------------------------------------------------------- #


def _classify_session_file(path: Path) -> _OfflineStatus:
    """
    Inspect a single ``.session`` file and return its offline status.

    Returns
    -------
    ``structurally_valid``
        Valid SQLite DB with a sessions row and non-empty auth_key.
    ``incomplete``
        Valid SQLite DB but missing a usable auth_key (deleted / wiped).
    ``invalid``
        Corrupt file, wrong format, or any structural error.
    """
    try:
        with sqlite3.connect(f"file:{path}?mode=ro", uri=True) as conn:
            conn.row_factory = sqlite3.Row

            table_row = conn.execute(
                "SELECT name FROM sqlite_master WHERE type='table' AND name='sessions'"
            ).fetchone()
            if table_row is None:
                return "invalid"

            data_row = conn.execute("SELECT auth_key FROM sessions LIMIT 1").fetchone()
            if data_row is None:
                return "incomplete"

            auth_key = data_row["auth_key"]
            if auth_key:
                return "structurally_valid"
            return "incomplete"

    except sqlite3.DatabaseError:
        return "invalid"
    except OSError:
        return "invalid"


def _detect_session_phone(path: Path) -> str | None:
    """Best-effort phone number from a session DB, or ``None``.

    Supports Telethon (``entities``), Pyrogram (``peers``) and generator
    ``users`` tables.  Never raises; any error means "no phone".
    """
    try:
        with sqlite3.connect(f"file:{path}?mode=ro", uri=True) as conn:
            tables = {
                row[0]
                for row in conn.execute(
                    "SELECT name FROM sqlite_master WHERE type='table'"
                )
            }
            for table in ("entities", "peers", "users"):
                if table not in tables:
                    continue
                cols = {row[1] for row in conn.execute(f"PRAGMA table_info({table})")}
                if "phone" not in cols:
                    continue
                row = conn.execute(
                    f"SELECT phone FROM {table} "
                    "WHERE phone IS NOT NULL AND phone != '' LIMIT 1"
                ).fetchone()
                if row and row[0]:
                    digits = re.sub(r"\D", "", str(row[0]))
                    if 7 <= len(digits) <= 15:
                        return digits
    except (sqlite3.DatabaseError, OSError):
        return None
    return None


def _extract_member_chunked(archive: zipfile.ZipFile, name: str, dest: Path) -> None:
    """Extract one ZIP member reading in _CHUNK_SIZE blocks to bound RAM."""
    with archive.open(name) as src, dest.open("wb") as dst:
        while True:
            chunk = src.read(_CHUNK_SIZE)
            if not chunk:
                break
            dst.write(chunk)


def _offline_statuses_from_zip(path: Path) -> list[_OfflineStatus]:
    """Validate a ZIP archive and return offline statuses for every .session member."""
    statuses: list[_OfflineStatus] = []

    try:
        with zipfile.ZipFile(path, "r") as archive:
            members = archive.infolist()

            if len(members) > _MAX_ZIP_MEMBERS:
                LOGGER.warning(
                    "ZIP rejected: %d members exceeds limit of %d",
                    len(members),
                    _MAX_ZIP_MEMBERS,
                )
                return ["invalid"]

            total_uncompressed = 0
            for info in members:
                member_path = Path(info.filename)
                if member_path.is_absolute() or ".." in member_path.parts:
                    LOGGER.warning("ZIP rejected: unsafe path in archive")
                    return ["invalid"]
                total_uncompressed += info.file_size
                if total_uncompressed > _MAX_ZIP_UNCOMPRESSED_BYTES:
                    LOGGER.warning(
                        "ZIP rejected: total uncompressed size exceeds limit"
                    )
                    return ["invalid"]
                if info.compress_size and info.file_size:
                    ratio = info.file_size / info.compress_size
                    if ratio > _MAX_COMPRESSION_RATIO:
                        LOGGER.warning(
                            "ZIP rejected: compression ratio %.1f exceeds limit", ratio
                        )
                        return ["invalid"]

            session_members = [
                m for m in members if m.filename.lower().endswith(".session")
            ]
            if not session_members:
                LOGGER.debug("ZIP contains no .session members")
                return ["invalid"]

            with tempfile.TemporaryDirectory(prefix="ftgc_sess_") as tmp:
                tmp_dir = Path(tmp)
                for info in session_members:
                    dest = tmp_dir / Path(info.filename).name
                    try:
                        _extract_member_chunked(archive, info.filename, dest)
                        statuses.append(_classify_session_file(dest))
                    except (OSError, zipfile.BadZipFile, KeyError):
                        LOGGER.debug("Failed to extract one .session member")
                        statuses.append("invalid")
                    finally:
                        dest.unlink(missing_ok=True)

    except zipfile.BadZipFile:
        return ["invalid"]
    except OSError as exc:
        LOGGER.error("I/O error while reading ZIP: %s", exc)
        return ["invalid"]

    return statuses


def _collect_offline_statuses(path: Path) -> list[_OfflineStatus]:
    """Dispatch to the correct handler; reject unsupported extensions."""
    suffix = path.suffix.lower()
    if suffix not in _ALLOWED_SUFFIXES:
        LOGGER.debug("Rejected unsupported extension: %r", suffix)
        return ["invalid"]
    if suffix == ".zip":
        return _offline_statuses_from_zip(path)
    return [_classify_session_file(path)]


# --------------------------------------------------------------------------- #
# Phase 2 – live spam check (async, optional)                                 #
# --------------------------------------------------------------------------- #


async def _live_status(
    session_path: Path,
    credentials: list[tuple[int, str]],
    timeout: int,
    proxy: tuple | None = None,
    credential_offset: int = 0,
) -> _FinalStatus:
    """
    Run the live @SpamBot check for one ``.session`` file.
    Delegates to ``app.services.spam.check_spam_via_spambot``.
    """
    from app.services.spam import check_spam_via_spambot

    return await check_spam_via_spambot(
        session_path,
        credentials,
        timeout,
        proxy=proxy,
        credential_offset=credential_offset,
    )


async def _resolve_final_status(
    session_path: Path,
    offline: _OfflineStatus,
    *,
    credentials: list[tuple[int, str]],
    timeout: int,
    proxy: tuple | None = None,
    credential_offset: int = 0,
) -> _FinalStatus:
    """
    Combine the offline result with the (optional) live spam check.

    An ``incomplete`` file (valid SQLite but wiped/empty auth_key) is the
    local fingerprint of a logged-out / killed session and is reported
    ``frozen`` from offline inspection alone; it is never mislabelled active.
    A structurally valid session without credentials is reported
    ``inconclusive`` — never ``active`` — because it was not verified live.
    """
    if offline == "incomplete":
        return "frozen"
    if offline == "invalid":
        return "invalid"

    # offline == "structurally_valid"
    if not credentials:
        # No credentials configured → cannot connect to Telegram servers.
        # Report inconclusive (never report unverified accounts as active).
        return "inconclusive"

    # Run live check against Telegram servers.
    try:
        return await _live_status(
            session_path,
            credentials,
            timeout,
            proxy=proxy,
            credential_offset=credential_offset,
        )
    except Exception:
        LOGGER.exception("Live spam check failed")
        return "inconclusive"


def _summarize(statuses: list[_FinalStatus]) -> SessionCheckResult:
    """
    Map final status labels to ``SessionCheckResult``.
    Invariant: checked == active + spam + frozen + banned + invalid + inconclusive.
    """
    return SessionCheckResult(
        checked=len(statuses),
        active=statuses.count("active"),
        spam=statuses.count("spam"),
        frozen=statuses.count("frozen"),
        banned=statuses.count("banned"),
        invalid=statuses.count("invalid"),
        inconclusive=statuses.count("inconclusive"),
    )


# --------------------------------------------------------------------------- #
# ZIP-specific async helper                                                    #
# --------------------------------------------------------------------------- #


async def _check_zip(
    path: Path,
    *,
    credentials: list[tuple[int, str]],
    timeout: int,
    proxy: tuple | None = None,
    progress: SessionProgress | None = None,
) -> list[SessionCheckEntry]:
    """
    Handle a ZIP archive: extract each .session, run both phases, return results.
    One failing member never aborts the rest.
    """
    try:
        with zipfile.ZipFile(path, "r") as archive:
            members = archive.infolist()

            if len(members) > _MAX_ZIP_MEMBERS:
                return [SessionCheckEntry("", "invalid")]

            total_uncompressed = 0
            for info in members:
                member_path = Path(info.filename)
                if member_path.is_absolute() or ".." in member_path.parts:
                    return [SessionCheckEntry("", "invalid")]
                total_uncompressed += info.file_size
                if total_uncompressed > _MAX_ZIP_UNCOMPRESSED_BYTES:
                    return [SessionCheckEntry("", "invalid")]
                if info.compress_size and info.file_size:
                    ratio = info.file_size / info.compress_size
                    if ratio > _MAX_COMPRESSION_RATIO:
                        return [SessionCheckEntry("", "invalid")]

            session_members = [
                m for m in members if m.filename.lower().endswith(".session")
            ]
            if not session_members:
                return [SessionCheckEntry("", "invalid")]

            if progress is not None:
                progress.total = len(session_members)

            sem = asyncio.Semaphore(40 if credentials else 50)

            with tempfile.TemporaryDirectory(prefix="ftgc_zip_") as tmp:
                tmp_dir = Path(tmp)

                async def _check_one_member(
                    idx: int, info: zipfile.ZipInfo
                ) -> SessionCheckEntry:
                    dest = tmp_dir / f"sess_{idx}_{Path(info.filename).name}"
                    try:
                        await asyncio.to_thread(
                            _extract_member_chunked, archive, info.filename, dest
                        )
                        offline = _classify_session_file(dest)
                        async with sem:
                            final = await _resolve_final_status(
                                dest,
                                offline,
                                credentials=credentials,
                                timeout=timeout,
                                proxy=proxy,
                                credential_offset=idx,
                            )
                        return SessionCheckEntry(
                            info.filename,
                            final,
                            phone=_detect_session_phone(dest),
                        )
                    except Exception:  # noqa: BLE001
                        LOGGER.debug("Failed to process one .session member in ZIP")
                        return SessionCheckEntry(info.filename, "invalid")
                    finally:
                        dest.unlink(missing_ok=True)
                        if progress is not None:
                            progress.done += 1

                entries = list(
                    await asyncio.gather(
                        *(
                            _check_one_member(idx, info)
                            for idx, info in enumerate(session_members)
                        )
                    )
                )

            return entries

    except zipfile.BadZipFile:
        return [SessionCheckEntry("", "invalid")]
    except OSError as exc:
        LOGGER.error("I/O error reading ZIP: %s", exc)
        return [SessionCheckEntry("", "invalid")]


# --------------------------------------------------------------------------- #
# Public async API                                                             #
# --------------------------------------------------------------------------- #


async def check_sessions(
    path: Path,
    *,
    credentials: list[tuple[int, str]] | None = None,
    timeout: int = 15,
    proxy: tuple | None = None,
    progress: SessionProgress | None = None,
) -> SessionCheckResult:
    """
    Classify all session files found at *path*.

    *path* must be a ``.session`` file or a ``.zip`` archive containing one
    or more ``.session`` files.  Any other extension → invalid.

    Parameters
    ----------
    path:
        Path to the uploaded file.
    credentials:
        List of ``(api_id, api_hash)`` pairs.  Each structurally valid session
        is checked live via @SpamBot using these credentials with automatic
        rotation on transient errors.  When ``None`` or empty, only the offline
        structural classification is returned.
    timeout:
        Seconds to wait for @SpamBot's reply during the live check.
    progress:
        Optional shared counter; ``total`` is set once the member count is
        known and ``done`` is incremented after every member finishes.

    Returns
    -------
    A ``SessionCheckResult`` always satisfying
    ``checked == active + spam + frozen + banned + invalid + inconclusive``.
    """
    result, _ = await check_sessions_detailed(
        path,
        credentials=credentials,
        timeout=timeout,
        proxy=proxy,
        progress=progress,
    )
    return result


async def check_sessions_detailed(
    path: Path,
    *,
    credentials: list[tuple[int, str]] | None = None,
    timeout: int = 15,
    proxy: tuple | None = None,
    progress: SessionProgress | None = None,
) -> tuple[SessionCheckResult, list[SessionCheckEntry]]:
    """
    Like :func:`check_sessions` but also returns per-session entries with the
    original member names, so callers can regroup the uploaded files by status.
    """
    creds: list[tuple[int, str]] = credentials or []
    suffix = path.suffix.lower()

    if suffix not in _ALLOWED_SUFFIXES:
        LOGGER.debug("Rejected unsupported extension: %r", suffix)
        return _summarize(["invalid"]), [SessionCheckEntry("", "invalid")]

    if suffix == ".zip":
        entries = await _check_zip(
            path,
            credentials=creds,
            timeout=timeout,
            proxy=proxy,
            progress=progress,
        )
        res = _summarize([e.status for e in entries])
        LOGGER.info(
            "Session check summary: Total=%d | Active=%d | Banned=%d | Spam=%d | Frozen=%d | Invalid=%d | Inconclusive=%d",
            res.checked,
            res.active,
            res.banned,
            res.spam,
            res.frozen,
            res.invalid,
            res.inconclusive,
        )
        return res, entries

    # Single .session file.
    offline = _classify_session_file(path)
    if progress is not None:
        progress.total = 1
    final = await _resolve_final_status(
        path, offline, credentials=creds, timeout=timeout, proxy=proxy
    )
    if progress is not None:
        progress.done = 1
    res = _summarize([final])
    proxy_name = "None"
    if isinstance(proxy, list) and proxy:
        proxy_name = f"Pool ({len(proxy)} proxies)"
    elif isinstance(proxy, tuple) and len(proxy) > 1:
        proxy_name = str(proxy[1])

    LOGGER.info(
        "Single session check: Total=1 | Status=%s | Proxy=%s",
        final,
        proxy_name,
    )
    return res, [SessionCheckEntry(path.name, final, phone=_detect_session_phone(path))]


# --------------------------------------------------------------------------- #
# Status ZIP separation                                                        #
# --------------------------------------------------------------------------- #

# Status → (file-name stem, display label).  Mirrors the reference bot's
# per-category archives ("📦 No Restriction - 9 accounts", "📦 Spam - 1 …").
# Spam-flagged and genuinely frozen accounts get their own archives.
_STATUS_ZIP_META: dict[str, tuple[str, str]] = {
    "active": ("No_Restriction", "No Restriction"),
    "spam": ("Spam", "Spam"),
    "frozen": ("Frozen", "Frozen"),
    "banned": ("Banned", "Banned"),
    "invalid": ("Invalid", "Invalid"),
    "inconclusive": ("Error", "Error"),
}


def _is_safe_member_name(name: str) -> bool:
    member_path = Path(name)
    return not member_path.is_absolute() and ".." not in member_path.parts


def build_status_zips(
    path: Path,
    entries: list[SessionCheckEntry],
    output_dir: Path,
    *,
    original_name: str | None = None,
) -> list[tuple[Path, str, int]]:
    """
    Regroup the checked sessions into one ZIP archive per status bucket.

    For a single ``.session`` upload the file is copied into its bucket under
    ``+<phone>.session`` when a phone number can be read from the session DB
    (falling back to *original_name* — the downloaded temp path is never
    leaked).  For a ZIP archive every member is written under its ORIGINAL
    relative path (so ``.session`` + sibling ``.json`` pairs stay together),
    grouped by the status of the account's ``.session`` member.

    Returns ``(zip_path, status, count)`` for every non-empty bucket, where
    *status* is one of the ``SessionCheckEntry`` status labels.
    """
    if not entries:
        return []
    if path.suffix.lower() != ".zip":
        # Single .session upload — name it by phone number when possible.
        entry = entries[0]
        meta = _STATUS_ZIP_META.get(entry.status)
        if meta is None:
            return []
        stem, _label = meta
        out = output_dir / f"{stem}_{1}.zip"
        if entry.phone:
            arcname = f"+{entry.phone}.session"
        else:
            arcname = Path(original_name or path.name).name
        with zipfile.ZipFile(out, "w", zipfile.ZIP_DEFLATED) as archive:
            archive.write(path, arcname=arcname)
        return [(out, entry.status, 1)]

    # Group ZIP members by account (path without extension) so siblings such
    # as ``123.session`` and ``123.json`` land in the same bucket.
    account_members: dict[str, list[zipfile.ZipInfo]] = {}
    try:
        with zipfile.ZipFile(path, "r") as archive:
            for info in archive.infolist():
                if not _is_safe_member_name(info.filename):
                    continue
                key = str(Path(info.filename).with_suffix(""))
                account_members.setdefault(key, []).append(info)
    except (zipfile.BadZipFile, OSError) as exc:
        LOGGER.error("Could not re-read ZIP for separation: %s", exc)
        return []

    counts: dict[str, int] = {}
    for entry in entries:
        if entry.member:
            counts[entry.status] = counts.get(entry.status, 0) + 1

    archives: list[tuple[Path, str, int]] = []
    try:
        src = zipfile.ZipFile(path, "r")
    except (zipfile.BadZipFile, OSError) as exc:
        LOGGER.error("Could not re-open ZIP for separation: %s", exc)
        return []
    with src:
        for status, (stem, _label) in _STATUS_ZIP_META.items():
            count = counts.get(status, 0)
            if count == 0:
                continue
            out = output_dir / f"{stem}_{count}.zip"
            written: set[str] = set()
            with zipfile.ZipFile(out, "w", zipfile.ZIP_DEFLATED) as archive:
                for entry in entries:
                    if entry.status != status or not entry.member:
                        continue
                    key = str(Path(entry.member).with_suffix(""))
                    for info in account_members.get(key, []):
                        if entry.phone:
                            arcname = f"+{entry.phone}{Path(info.filename).suffix}"
                        else:
                            arcname = info.filename
                        if arcname in written:
                            continue
                        written.add(arcname)
                        try:
                            new_info = zipfile.ZipInfo(arcname)
                            new_info.date_time = info.date_time
                            new_info.compress_type = info.compress_type
                            new_info.external_attr = info.external_attr
                            archive.writestr(new_info, src.read(info.filename))
                        except (OSError, KeyError, RuntimeError) as exc:
                            LOGGER.debug(
                                "Skipping member %r during separation: %s",
                                info.filename,
                                exc,
                            )
            archives.append((out, status, count))
    return archives
