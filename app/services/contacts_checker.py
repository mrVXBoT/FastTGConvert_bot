"""
Contact checker for Telethon ``.session`` accounts.

Classifies every account as one of:

* ``ok``          – connected, authorized and can read its profile/contacts
* ``limited``     – the account is restricted: Telegram explicitly rejects
                         reading (privacy / flood / restriction) or @SpamBot
                         reports a restriction
* ``2fa``         – account is protected by a 2FA password (session unusable)
* ``banned``      – account is banned / deactivated / auth key duplicated
* ``invalid``     – corrupt session, expired / revoked auth key, invalid API id
* ``inconclusive``– transient network / flood / timeout; structural check failed
                        → invalid, else reported honestly as inconclusive

The 6 internal statuses map to 4 user-facing buckets (matching the
industry-standard 4-way report):

* Healthy    ← ``ok``
* Restricted ← ``limited``
* Invalid    ← ``invalid`` + ``banned`` + ``2fa``
* Error      ← ``inconclusive``

Notes:

* Classification is read-first: an account is Healthy when it can connect
  and read its own profile; write probes do NOT downgrade an account.
* ``AuthKeyDuplicatedError`` / ``PhoneNumberBannedError`` are classified
  as banned (→ Invalid for users).
* A 2FA-protected account is detected (``account.getPassword`` probe) and
  reported under the Invalid bucket.
* Transient network errors / FloodWait are never treated as OK: the next
  credential is tried, small flood waits are honoured, and a session that
  never succeeds is reported inconclusive (→ Error), or ``invalid`` when
  the offline structural check also fails.
* Each session is checked under a per-session timeout, several sessions run
  concurrently, the job can be cancelled, and live progress (done / total)
  is reported through a callback object.
* Sibling files (e.g. ``123.session`` + ``123.json``) are kept together in
  the per-status ZIP archives and original member names are restored.
* A CSV report with the per-account profile (phone, username, names,
  premium, DC, contacts count) is generated alongside the status ZIPs.
"""

from __future__ import annotations

import asyncio
import csv
import logging
import shutil
import sqlite3
import tempfile
import zipfile
from contextlib import suppress
from dataclasses import dataclass, field
from pathlib import Path
from typing import Literal
from uuid import uuid4

from app.services.files import (
    MAX_COMPRESSION_RATIO,
    MAX_ZIP_MEMBERS,
    MAX_ZIP_UNCOMPRESSED_BYTES,
    UnsafeArchiveError,
)

LOGGER = logging.getLogger(__name__)

ContactStatus = Literal[
    "ok", "limited", "2fa", "banned", "invalid", "inconclusive"
]

# Status -> (ZIP file-name stem, report Status column).  Several internal
# statuses collapse into the 4 user-facing buckets.
_STATUS_ZIP_STEM: dict[ContactStatus, str] = {
    "ok": "Check_contacts_Healthy",
    "limited": "Check_contacts_Restricted",
    "2fa": "Check_contacts_Invalid",
    "banned": "Check_contacts_Invalid",
    "invalid": "Check_contacts_Invalid",
    "inconclusive": "Check_contacts_Error",
}

_STATUS_BUCKET_LABEL: dict[ContactStatus, str] = {
    "ok": "Healthy",
    "limited": "Restricted",
    "2fa": "Invalid",
    "banned": "Invalid",
    "invalid": "Invalid",
    "inconclusive": "Error",
}


class ContactsCheckCancelled(Exception):
    """Raised when the user cancels a running contacts check."""


@dataclass
class ContactsProgress:
    """Shared mutable progress state for a running contacts check."""

    total: int = 0
    done: int = 0


@dataclass(frozen=True)
class ContactAccountInfo:
    """Profile details captured for an account that checked OK."""

    contacts_count: int = 0
    phone: str = ""
    username: str = ""
    first_name: str = ""
    last_name: str = ""
    premium: bool = False
    dc_id: int | None = None


@dataclass(frozen=True)
class ContactCheckEntry:
    """Per-session check outcome."""

    name: str
    status: ContactStatus
    info: ContactAccountInfo | None = None


@dataclass(frozen=True)
class ContactsCheckResult:
    checked: int = 0
    ok: int = 0
    limited: int = 0
    two_fa: int = 0
    banned: int = 0
    invalid: int = 0
    inconclusive: int = 0
    entries: tuple[ContactCheckEntry, ...] = ()
    zip_paths: tuple[tuple[Path, ContactStatus, int], ...] = ()
    report_path: Path | None = None

    def __post_init__(self) -> None:
        total = (
            self.ok
            + self.limited
            + self.two_fa
            + self.banned
            + self.invalid
            + self.inconclusive
        )
        if total != self.checked:
            raise ValueError(f"checked ({self.checked}) != sum of buckets ({total})")


@dataclass(frozen=True)
class _ExtractedSession:
    """One extracted account: its session file plus sibling files (.json…)."""

    session_path: Path
    member_name: str
    files: tuple[tuple[Path, str], ...] = field(
        default_factory=tuple
    )  # (extracted_path, original_archive_name)


# --------------------------------------------------------------------------- #
# Live check                                                                  #
# --------------------------------------------------------------------------- #


def _pick_errors(tl_errors: object, names: tuple[str, ...]) -> tuple[type, ...]:
    """Collect error classes by name, skipping any missing in this telethon."""
    picked: list[type] = []
    for name in names:
        cls = getattr(tl_errors, name, None)
        if cls is not None:
            picked.append(cls)
    return tuple(picked)


async def _fetch_me_profile(client: object, contacts_count: int) -> ContactAccountInfo:
    """Fetch the account's own profile (phone, username, names, DC…)."""
    from telethon.tl.functions.users import (
        GetUsersRequest,  # type: ignore[import-untyped]
    )
    from telethon.tl.types import InputUserSelf  # type: ignore[import-untyped]

    info = ContactAccountInfo(contacts_count=contacts_count)
    try:
        res = await client(GetUsersRequest([InputUserSelf()]))  # type: ignore[operator]
        user = res.users[0] if getattr(res, "users", None) else None
        if user is None:
            return info
        return ContactAccountInfo(
            contacts_count=contacts_count,
            phone=str(getattr(user, "phone", "") or ""),
            username=str(getattr(user, "username", "") or ""),
            first_name=str(getattr(user, "first_name", "") or ""),
            last_name=str(getattr(user, "last_name", "") or ""),
            premium=bool(getattr(user, "premium", False)),
            dc_id=getattr(user, "dc_id", None),
        )
    except Exception as exc:  # noqa: BLE001
        LOGGER.debug("Profile fetch failed for a session: %s", exc)
        return info


def _is_limitation_error(exc: Exception) -> bool:
    """True when an error signals the account is write-restricted / limited.

    A connectable-but-limited account is revealed by its attempt to mutate
    the contacts store: it is throttled, privacy-blocked or forced into a
    take-out mode.  These surface as flood/privacy/take-out restrictions,
    distinct from a hard ban.
    """
    code = getattr(exc, "code", None)
    text = f"{type(exc).__name__} {exc}".upper()
    if code == 420:  # FLOOD_WAIT
        return True
    return any(
        keyword in text
        for keyword in (
            "FLOOD",
            "RESTRICTED",
            "USERS_TOO_FEW",
            "PRIVACY",
            "TAKEOUT_REQUIRED",
            "TAKEOUT_INIT",
            "CONTACT_ADD_MISSING_FEATURE",
            "LIMITED",
        )
    )


async def _probe_add_contact(
    client: object,
    *,
    banned_errors: tuple[type, ...] | None = None,
    invalid_errors: tuple[type, ...] | None = None,
) -> ContactStatus:
    """
    Read-first permission probe.

    Classification is read-based (an account is Healthy when it can connect
    and read); kept as a thin no-op wrapper so the read path never downgrades
    an account because of a write attempt.
    """
    return "ok"


async def check_session_contacts_live(
    session_path: Path,
    credentials: list[tuple[int, str]],
    proxy: tuple | None = None,
    *,
    flood_wait_ceiling: int = 5,
    credential_offset: int = 0,
) -> tuple[ContactStatus, ContactAccountInfo | None]:
    """
    Connect via Telethon, probe 2FA, fetch the contacts count and the
    account profile.

    Returns ``(status, info)`` where *info* is populated only for ``ok``.
    Transient errors (network, flood, timeout) fall through to the next
    credential; ``inconclusive`` is returned when every credential failed.
    """
    if not credentials or not session_path.exists():
        return "inconclusive", None

    # Round-robin the starting credential so concurrent sessions do not all
    # pile onto the first api_id at the same moment.
    if credential_offset:
        offset = credential_offset % len(credentials)
        if offset:
            credentials = credentials[offset:] + credentials[:offset]

    try:
        # fmt: off
        from telethon import TelegramClient  # type: ignore[import-untyped]
        from telethon import errors as tl_errors
        from telethon.tl.functions.account import (
            GetPasswordRequest,  # type: ignore[import-untyped]
        )
        from telethon.tl.functions.contacts import (
            GetContactsRequest,  # type: ignore[import-untyped]
        )
        # fmt: on
    except ModuleNotFoundError:
        LOGGER.error("Telethon not installed for contacts check")
        return "inconclusive", None

    banned_errors = _pick_errors(
        tl_errors,
        (
            "AuthKeyDuplicatedError",
            "PhoneNumberBannedError",
            "UserBannedError",
            "UserDeactivatedError",
        ),
    )
    invalid_errors = _pick_errors(
        tl_errors,
        (
            "AuthKeyInvalidError",
            "AuthKeyUnregisteredError",
            "SessionRevokedError",
            "SessionExpiredError",
            "ApiIdInvalidError",
        ),
    )
    flood_error = getattr(tl_errors, "FloodWaitError", None)
    password_errors = _pick_errors(tl_errors, ("SessionPasswordNeededError",))
    db_errors = (sqlite3.DatabaseError, sqlite3.OperationalError)

    with tempfile.TemporaryDirectory(prefix="ftgc_cntread_") as tmp:
        tmp_session = Path(tmp) / "read.session"
        shutil.copy2(session_path, tmp_session)
        session_str = str(tmp_session.with_suffix(""))

        for api_id, api_hash in credentials:
            for _attempt in range(3):
                try:
                    from app.services.device_params import get_stable_device_params
                    device_kwargs = get_stable_device_params(session_path)

                    client = TelegramClient(  # type: ignore[call-arg]
                        session_str,
                        api_id,
                        api_hash,
                        receive_updates=False,
                        proxy=proxy,
                        **device_kwargs,
                    )
                    await client.connect()
                    if not await client.is_user_authorized():
                        # Probe whether the account is protected by a 2FA
                        # password instead of assuming it is simply dead.
                        pwd = await client(GetPasswordRequest())
                        if getattr(pwd, "current_algo", None) is not None:
                            return "2fa", None
                        return "banned", None

                    res = await client(GetContactsRequest(hash=0))
                    count = len(getattr(res, "contacts", []))
                    info = await _fetch_me_profile(client, count)

                    # Secondary probe: check @SpamBot for spam restrictions
                    with suppress(Exception):
                        from app.services.spam import (
                            _parse_spambot_reply,
                            _spambot_status_reply,
                        )
                        spambot_reply = await _spambot_status_reply(
                            client, timeout=5, FloodWaitError=flood_error or Exception
                        )
                        if spambot_reply:
                            spam_st = _parse_spambot_reply(spambot_reply)
                            if spam_st in ("spam", "frozen"):
                                return "limited", None
                            if spam_st == "banned":
                                return "banned", None

                    return "ok", info
                except password_errors:
                    return "2fa", None
                except banned_errors:
                    LOGGER.debug(
                        "Contacts check banned/deactivated with api_id=%d", api_id
                    )
                    return "banned", None
                except invalid_errors:
                    LOGGER.debug("Contacts check invalid auth with api_id=%d", api_id)
                    return "invalid", None
                except db_errors:
                    LOGGER.debug(
                        "Contacts check corrupt session db with api_id=%d", api_id
                    )
                    return "invalid", None
                except Exception as exc:  # noqa: BLE001
                    if _is_limitation_error(exc) and not (
                        flood_error is not None and isinstance(exc, flood_error)
                    ):
                        LOGGER.debug(
                            "Contacts check restricted with api_id=%d: %s", api_id, exc
                        )
                        return "limited", None
                    if (
                        flood_error is not None
                        and isinstance(exc, flood_error)
                        and getattr(exc, "seconds", 0) <= flood_wait_ceiling
                    ):
                        # Small flood wait: honour it and retry this credential.
                        LOGGER.warning(
                            "FloodWait %ss during contacts check (api_id=%d)",
                            getattr(exc, "seconds", "?"),
                            api_id,
                        )
                        await asyncio.sleep(float(getattr(exc, "seconds", 1)))
                        continue
                    LOGGER.warning(
                        "Contacts check transient error with api_id=%d: %s",
                        api_id,
                        exc,
                    )
                    break
                finally:
                    if client is not None:
                        with suppress(Exception):
                            await client.disconnect()

    return "inconclusive", None


# --------------------------------------------------------------------------- #
# Offline structural check                                                     #
# --------------------------------------------------------------------------- #


def check_session_contacts_offline(session_path: Path) -> tuple[bool, int]:
    """
    Offline check of sqlite session file for validity and contacts count.
    Returns (is_ok, contacts_count).
    A valid session requires a sessions table with non-empty auth_key.
    If contacts table exists, returns contact count; otherwise returns 0 contacts for valid session.
    """
    if not session_path.exists():
        return False, 0

    with (
        suppress(Exception),
        sqlite3.connect(f"file:{session_path}?mode=ro", uri=True) as conn,
    ):
        conn.row_factory = sqlite3.Row
        sess_row = conn.execute(
            "SELECT name FROM sqlite_master WHERE type='table' AND name='sessions'"
        ).fetchone()
        if not sess_row:
            return False, 0

        auth = conn.execute("SELECT auth_key FROM sessions LIMIT 1").fetchone()
        if not auth or not auth["auth_key"] or len(auth["auth_key"]) < 16:
            return False, 0

        cnt_row = conn.execute(
            "SELECT name FROM sqlite_master WHERE type='table' AND name='contacts'"
        ).fetchone()
        if cnt_row:
            count_res = conn.execute("SELECT COUNT(*) as c FROM contacts").fetchone()
            count = count_res["c"] if count_res else 0
            return True, count

        return True, 0

    return False, 0


# --------------------------------------------------------------------------- #
# ZIP extraction (sessions + siblings)                                         #
# --------------------------------------------------------------------------- #


def _extract_member_chunked(
    archive: zipfile.ZipFile, info: zipfile.ZipInfo, dest: Path
) -> None:
    """Extract one ZIP member reading in 256 KiB chunks to bound RAM usage."""
    chunk_size = 256 * 1024
    with archive.open(info) as src, dest.open("wb") as dst:
        while True:
            chunk = src.read(chunk_size)
            if not chunk:
                break
            dst.write(chunk)


def extract_zip_sessions_safe(zip_path: Path, target_dir: Path) -> list[Path]:
    """
    Safely extract the ``.session`` members from a ZIP with Zip Slip & Zip
    Bomb guards.

    Returns the extracted file paths (renamed ``session_<idx>_<name>``).
    Returns an empty list when the archive contains no ``.session`` files.
    """
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

        session_files: list[Path] = []
        for idx, info in enumerate(members):
            if Path(info.filename).suffix.lower() != ".session":
                continue
            dest = target_dir / f"session_{idx}_{Path(info.filename).name}"
            _extract_member_chunked(archive, info, dest)
            session_files.append(dest)

    return session_files


def extract_accounts_safe(zip_path: Path, target_dir: Path) -> list[_ExtractedSession]:
    """
    Safely extract accounts (session + sibling files) from a ZIP.

    Files are grouped by their path without extension so sibling files
    (e.g. ``123.session`` + ``123.json``) stay together.  Every group that
    contains a ``.session`` member becomes one ``_ExtractedSession``.

    Raises ``UnsafeArchiveError("zip_no_sessions")`` when the archive
    contains no ``.session`` files at all.
    """
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

        groups: dict[str, list[zipfile.ZipInfo]] = {}
        for info in members:
            key = str(Path(info.filename).with_suffix(""))
            groups.setdefault(key, []).append(info)

        extracted: list[_ExtractedSession] = []
        for idx, (key, infos) in enumerate(groups.items()):
            sessions = [
                i for i in infos if Path(i.filename).suffix.lower() == ".session"
            ]
            if not sessions:
                continue
            files: list[tuple[Path, str]] = []
            session_path: Path | None = None
            for info in infos:
                dest = target_dir / f"session_{idx}_{Path(info.filename).name}"
                _extract_member_chunked(archive, info, dest)
                files.append((dest, info.filename))
                if info in sessions:
                    session_path = dest
            if session_path is None:
                continue
            extracted.append(
                _ExtractedSession(
                    session_path=session_path,
                    member_name=sessions[0].filename,
                    files=tuple(files),
                )
            )

    if not extracted:
        raise UnsafeArchiveError("zip_no_sessions")
    return extracted


# --------------------------------------------------------------------------- #
# Outputs: per-status ZIPs + CSV report                                        #
# --------------------------------------------------------------------------- #


def build_contacts_zips(
    extracted: list[_ExtractedSession],
    entries: list[ContactCheckEntry],
    output_dir: Path,
) -> list[tuple[Path, ContactStatus, int]]:
    """
    Build one ZIP per user-facing bucket from the extracted account files.

    Original member names (and relative paths) are restored inside the
    archives so ``123.session`` + ``123.json`` pairs stay together.
    """
    if not extracted or not entries:
        return []

    buckets: dict[str, list[tuple[_ExtractedSession, ContactCheckEntry]]] = {}
    for ex, entry in zip(extracted, entries, strict=False):
        stem = _STATUS_ZIP_STEM[entry.status]
        buckets.setdefault(stem, []).append((ex, entry))

    archives: list[tuple[Path, ContactStatus, int]] = []
    for stem, matched in buckets.items():
        out = output_dir / f"{stem}_{len(matched)}_{uuid4().hex[:8]}.zip"
        with zipfile.ZipFile(out, "w", zipfile.ZIP_DEFLATED) as archive:
            for ex, _entry in matched:
                for extracted_path, original_name in ex.files:
                    archive.write(extracted_path, arcname=original_name)
        archives.append((out, matched[0][1].status, len(matched)))
    return archives


_REPORT_HEADERS = [
    "#",
    "File",
    "Status",
    "Contacts",
    "Phone",
    "Username",
    "First Name",
    "Last Name",
    "Premium",
    "DC",
    "Note",
]

_REPORT_STATUS_NOTES: dict[ContactStatus, str] = {
    "ok": "",
    "limited": "Restricted / read permission denied",
    "2fa": "2FA password required",
    "banned": "Banned / deactivated",
    "invalid": "Invalid / expired session",
    "inconclusive": "Network error / timeout — retry",
}


def build_contacts_report(entries: list[ContactCheckEntry], output_dir: Path) -> Path:
    """Write a UTF-8 CSV report (with BOM for Excel) of every checked account."""
    report_path = output_dir / f"contacts_report_{uuid4().hex[:8]}.csv"
    with report_path.open("w", newline="", encoding="utf-8-sig") as handle:
        writer = csv.writer(handle)
        writer.writerow(_REPORT_HEADERS)
        for idx, entry in enumerate(entries, start=1):
            info = entry.info
            writer.writerow(
                [
                    idx,
                    entry.name,
                    _STATUS_BUCKET_LABEL.get(entry.status, entry.status),
                    info.contacts_count if info else "",
                    info.phone if info else "",
                    info.username if info else "",
                    info.first_name if info else "",
                    info.last_name if info else "",
                    "yes" if info and info.premium else "",
                    info.dc_id if info and info.dc_id is not None else "",
                    _REPORT_STATUS_NOTES.get(entry.status, ""),
                ]
            )
    return report_path


# --------------------------------------------------------------------------- #
# Orchestration                                                                #
# --------------------------------------------------------------------------- #


async def process_contacts_check(
    input_path: Path,
    output_dir: Path,
    credentials: list[tuple[int, str]] | None = None,
    proxy: tuple | None = None,
    *,
    concurrency: int = 3,
    per_session_timeout: int = 30,
    flood_wait_ceiling: int = 5,
    progress: ContactsProgress | None = None,
    cancel_event: asyncio.Event | None = None,
) -> ContactsCheckResult:
    """
    Check every account in *input_path* (single ``.session`` or ``.zip``).

    Live checks run concurrently (bounded by *concurrency*); each session is
    bounded by *per_session_timeout*.  Transient failures try the remaining
    credentials and are finally reported ``inconclusive`` unless the offline
    structural check also fails (→ ``invalid``).

    When *cancel_event* is set, the remaining sessions are skipped and
    :class:`ContactsCheckCancelled` is raised.
    """
    extracted: list[_ExtractedSession] = []
    temp_dir: tempfile.TemporaryDirectory[str] | None = None
    try:
        if input_path.suffix.lower() == ".zip":
            temp_dir = tempfile.TemporaryDirectory(prefix="ftgc_cntzip_")
            extracted = await asyncio.to_thread(
                extract_accounts_safe, input_path, Path(temp_dir.name)
            )
        else:
            extracted = [
                _ExtractedSession(
                    session_path=input_path,
                    member_name=input_path.name,
                    files=((input_path, input_path.name),),
                )
            ]

        total = len(extracted)
        if progress is not None:
            progress.total = total

        sem = asyncio.Semaphore(concurrency)
        cancelled = False

        async def worker(index: int, ex: _ExtractedSession) -> ContactCheckEntry | None:
            nonlocal cancelled
            if cancelled:
                return None
            async with sem:
                if cancel_event is not None and cancel_event.is_set():
                    cancelled = True
                    return None
                status, info = await _check_one_session(
                    ex.session_path,
                    credentials=credentials,
                    proxy=proxy,
                    per_session_timeout=per_session_timeout,
                    flood_wait_ceiling=flood_wait_ceiling,
                    credential_offset=index,
                )
                if progress is not None:
                    progress.done += 1
                return ContactCheckEntry(name=ex.member_name, status=status, info=info)

        results = await asyncio.gather(
            *(worker(index, ex) for index, ex in enumerate(extracted))
        )
        entries = [entry for entry in results if entry is not None]
        if cancelled:
            raise ContactsCheckCancelled()

        checked = len(entries)
        counts = {
            status: sum(1 for e in entries if e.status == status)
            for status in _STATUS_ZIP_STEM
        }
        result = ContactsCheckResult(
            checked=checked,
            ok=counts["ok"],
            limited=counts["limited"],
            two_fa=counts["2fa"],
            banned=counts["banned"],
            invalid=counts["invalid"],
            inconclusive=counts["inconclusive"],
            entries=tuple(entries),
        )

        output_dir.mkdir(parents=True, exist_ok=True)
        zip_paths = await asyncio.to_thread(
            build_contacts_zips, extracted, entries, output_dir
        )
        report_path = (
            await asyncio.to_thread(build_contacts_report, entries, output_dir)
            if entries
            else None
        )
        return ContactsCheckResult(
            checked=result.checked,
            ok=result.ok,
            limited=result.limited,
            two_fa=result.two_fa,
            banned=result.banned,
            invalid=result.invalid,
            inconclusive=result.inconclusive,
            entries=result.entries,
            zip_paths=tuple(zip_paths),
            report_path=report_path,
        )
    finally:
        if temp_dir is not None:
            temp_dir.cleanup()


async def _check_one_session(
    session_path: Path,
    *,
    credentials: list[tuple[int, str]] | None,
    proxy: tuple | None,
    per_session_timeout: int,
    flood_wait_ceiling: int,
    credential_offset: int = 0,
) -> tuple[ContactStatus, ContactAccountInfo | None]:
    """Check a single extracted session file (live with offline fallback)."""
    if credentials:
        try:
            status, info = await asyncio.wait_for(
                check_session_contacts_live(
                    session_path,
                    credentials,
                    proxy=proxy,
                    flood_wait_ceiling=flood_wait_ceiling,
                    credential_offset=credential_offset,
                ),
                timeout=per_session_timeout,
            )
        except TimeoutError:
            LOGGER.warning("Contacts check timed out for %s", session_path.name)
            status, info = "inconclusive", None
        if status == "inconclusive":
            # Never pretend a broken session is OK: a structurally invalid
            # file is reported invalid even when the network is flaky.
            offline_ok, _ = await asyncio.to_thread(
                check_session_contacts_offline, session_path
            )
            if not offline_ok:
                status = "invalid"
        return status, info

    # No API credentials configured: the account cannot be checked against
    # Telegram.  Never report a local-only structural check as "ok" — a
    # structurally sound file is reported inconclusive, a broken one invalid.
    offline_ok, _ = await asyncio.to_thread(
        check_session_contacts_offline, session_path
    )
    if offline_ok:
        return "inconclusive", None
    return "invalid", None
