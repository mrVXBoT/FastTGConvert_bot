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
| structurally_valid  | frozen              | frozen                     |
| structurally_valid  | banned              | banned                     |
| structurally_valid  | invalid             | invalid                    |
| structurally_valid  | inconclusive        | inconclusive               |
| structurally_valid  | (no credentials)    | active  ← offline only     |
| incomplete          | (skipped)           | frozen                     |
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

import logging
import sqlite3
import tempfile
import zipfile
from pathlib import Path
from typing import Literal

from app.session_results import SessionCheckResult

__all__ = ["check_sessions"]

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
_FinalStatus = Literal["active", "frozen", "banned", "invalid", "inconclusive"]


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
) -> _FinalStatus:
    """
    Run the live @SpamBot check for one ``.session`` file.
    Delegates to ``app.services.spam.check_spam_via_spambot``.
    """
    from app.services.spam import check_spam_via_spambot

    return await check_spam_via_spambot(session_path, credentials, timeout, proxy=proxy)


async def _resolve_final_status(
    session_path: Path,
    offline: _OfflineStatus,
    *,
    credentials: list[tuple[int, str]],
    timeout: int,
    proxy: tuple | None = None,
) -> _FinalStatus:
    """
    Combine the offline result with the (optional) live spam check.

    If no credentials are configured, only the offline result is used
    (structurally_valid → active, incomplete → frozen).
    """
    if offline == "incomplete":
        return "frozen"
    if offline == "invalid":
        return "invalid"

    # offline == "structurally_valid"
    if not credentials:
        # No credentials → report as active (structural only).
        return "active"

    # Run live check.
    try:
        return await _live_status(session_path, credentials, timeout, proxy=proxy)
    except Exception:
        LOGGER.exception("Live spam check failed; falling back to structural result")
        return "active"


def _summarize(statuses: list[_FinalStatus]) -> SessionCheckResult:
    """
    Map final status labels to ``SessionCheckResult``.
    Invariant: checked == active + frozen + banned + invalid + inconclusive.
    """
    return SessionCheckResult(
        checked=len(statuses),
        active=statuses.count("active"),
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
) -> list[_FinalStatus]:
    """
    Handle a ZIP archive: extract each .session, run both phases, return results.
    One failing member never aborts the rest.
    """
    try:
        with zipfile.ZipFile(path, "r") as archive:
            members = archive.infolist()

            if len(members) > _MAX_ZIP_MEMBERS:
                return ["invalid"]

            total_uncompressed = 0
            for info in members:
                member_path = Path(info.filename)
                if member_path.is_absolute() or ".." in member_path.parts:
                    return ["invalid"]
                total_uncompressed += info.file_size
                if total_uncompressed > _MAX_ZIP_UNCOMPRESSED_BYTES:
                    return ["invalid"]
                if info.compress_size and info.file_size:
                    ratio = info.file_size / info.compress_size
                    if ratio > _MAX_COMPRESSION_RATIO:
                        return ["invalid"]

            session_members = [
                m for m in members if m.filename.lower().endswith(".session")
            ]
            if not session_members:
                return ["invalid"]

            results: list[_FinalStatus] = []
            with tempfile.TemporaryDirectory(prefix="ftgc_zip_") as tmp:
                tmp_dir = Path(tmp)
                for info in session_members:
                    dest = tmp_dir / Path(info.filename).name
                    try:
                        _extract_member_chunked(archive, info.filename, dest)
                        offline = _classify_session_file(dest)
                        final = await _resolve_final_status(
                            dest,
                            offline,
                            credentials=credentials,
                            timeout=timeout,
                            proxy=proxy,
                        )
                        results.append(final)
                    except Exception:  # noqa: BLE001
                        LOGGER.debug("Failed to process one .session member in ZIP")
                        results.append("invalid")
                    finally:
                        dest.unlink(missing_ok=True)

            return results

    except zipfile.BadZipFile:
        return ["invalid"]
    except OSError as exc:
        LOGGER.error("I/O error reading ZIP: %s", exc)
        return ["invalid"]


# --------------------------------------------------------------------------- #
# Public async API                                                             #
# --------------------------------------------------------------------------- #


async def check_sessions(
    path: Path,
    *,
    credentials: list[tuple[int, str]] | None = None,
    timeout: int = 15,
    proxy: tuple | None = None,
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

    Returns
    -------
    A ``SessionCheckResult`` where
    ``checked == active + frozen + invalid`` is always satisfied.
    """
    creds: list[tuple[int, str]] = credentials or []
    suffix = path.suffix.lower()

    if suffix not in _ALLOWED_SUFFIXES:
        LOGGER.debug("Rejected unsupported extension: %r", suffix)
        return _summarize(["invalid"])

    if suffix == ".zip":
        statuses = await _check_zip(path, credentials=creds, timeout=timeout, proxy=proxy)
        return _summarize(statuses)

    # Single .session file.
    offline = _classify_session_file(path)
    final = await _resolve_final_status(
        path, offline, credentials=creds, timeout=timeout, proxy=proxy
    )
    return _summarize([final])
