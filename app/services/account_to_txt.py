from __future__ import annotations

import asyncio
import errno
import logging
import re
import shutil
import sqlite3
import tempfile
import zipfile
from contextlib import suppress
from dataclasses import dataclass, replace
from datetime import datetime, timezone
from pathlib import Path
from typing import Literal
from uuid import uuid4

UTC = timezone.utc  # noqa: UP017  (py<3.11 compat)

from app.services.files import (
    MAX_COMPRESSION_RATIO,
    MAX_ZIP_MEMBERS,
    MAX_ZIP_UNCOMPRESSED_BYTES,
    UnsafeArchiveError,
)
from app.services.jobs import JobCancelled, JobProgress

LOGGER = logging.getLogger(__name__)

AccountStatus = Literal["active", "invalid", "failed"]

_SIDECAR_PASSWORD_NAMES = ("password.txt", "2fa.txt", "twofa.txt", "password")

# Max concurrent network probes. Probes share the global api_credential pairs
# (and thus one IP / api_id), so keep the ceiling low to avoid flood bans.
_PROBE_CONCURRENCY = 8


@dataclass(frozen=True)
class AccountProfile:
    identifier: str
    phone: str
    username: str
    full_name: str
    user_id: int
    premium: bool = False
    dc_id: int | None = None
    two_fa: bool | None = None
    registered: str = "N/A"


@dataclass(frozen=True)
class AccountTxtEntry:
    profile: AccountProfile
    status: AccountStatus
    authorized: bool
    reason: str = ""

    @property
    def report_icon(self) -> str:
        return "✅" if self.authorized else "⚠️"


@dataclass(frozen=True)
class AccountTxtResult:
    total: int
    active: int
    invalid_converted: int
    failed: int
    output_zip_path: Path | None = None
    phones_path: Path | None = None
    status_path: Path | None = None
    entries: tuple[AccountTxtEntry, ...] = ()

    @property
    def converted(self) -> int:
        # Only authorized sessions count as converted; invalid (banned /
        # deactivated) entries are not usable accounts.
        return self.active


def _clean_value(value: object, fallback: str = "N/A") -> str:
    cleaned = (
        str(value or "").replace("|", " ").replace("\r", " ").replace("\n", " ").strip()
    )
    return cleaned or fallback


def _epoch_date(value: object) -> str:
    try:
        if isinstance(value, (int, float, str)):
            ts = int(value)
        else:
            ts = 0
    except (TypeError, ValueError):
        return "N/A"
    if ts < 946684800:  # year 2000 sanity floor
        return "N/A"
    return datetime.fromtimestamp(ts, tz=UTC).strftime("%Y-%m-%d")


def render_account_line(profile: AccountProfile) -> str:
    return "|".join(
        (
            _clean_value(profile.identifier),
            _clean_value(profile.phone),
            _clean_value(profile.username),
            _clean_value(profile.full_name),
            str(profile.user_id),
            "1" if profile.premium else "0",
            _clean_value(profile.dc_id if profile.dc_id is not None else "N/A"),
            "1" if profile.two_fa else ("0" if profile.two_fa is False else "N/A"),
            _clean_value(profile.registered),
        )
    )


def _original_stem(path: Path) -> str:
    stem = path.stem
    match = re.fullmatch(r"session_\d+_(\d{7,15})", stem)
    if match:
        return match.group(1)
    return stem


def _fallback_profile(path: Path) -> AccountProfile | None:
    stem = _original_stem(path)
    digits_match = re.search(r"(\d{7,15})", stem)
    if not digits_match:
        return None
    digits = digits_match.group(1)
    return AccountProfile(
        identifier=digits,
        phone=f"+{digits}",
        username="N/A",
        full_name="N/A",
        user_id=0,
    )


def _placeholder_profile(path: Path) -> AccountProfile:
    profile = _fallback_profile(path)
    if profile is not None:
        return profile
    return AccountProfile(
        identifier=path.stem,
        phone="N/A",
        username="N/A",
        full_name="N/A",
        user_id=0,
    )


def _is_structural_session(path: Path) -> bool:
    try:
        with sqlite3.connect(f"file:{path}?mode=ro", uri=True) as conn:
            row = conn.execute("SELECT auth_key FROM sessions LIMIT 1").fetchone()
            return bool(row and row[0] and len(row[0]) == 256)
    except (sqlite3.DatabaseError, OSError):
        return False


def _is_pyrogram_session(path: Path) -> bool:
    try:
        with sqlite3.connect(f"file:{path}?mode=ro", uri=True) as conn:
            tables = {
                row[0]
                for row in conn.execute(
                    "SELECT name FROM sqlite_master WHERE type='table'"
                ).fetchall()
            }
            if "sessions" not in tables or "version" in tables:
                return False
            cols = {row[1] for row in conn.execute("PRAGMA table_info(sessions)")}
            return "user_id" in cols
    except (sqlite3.DatabaseError, OSError):
        return False


def _pyrogram_offline_profile(path: Path) -> AccountProfile | None:
    try:
        with sqlite3.connect(f"file:{path}?mode=ro", uri=True) as conn:
            conn.row_factory = sqlite3.Row
            row = conn.execute("SELECT * FROM sessions LIMIT 1").fetchone()
            if row is None or not row["auth_key"]:
                return None
            user_id = int(row["user_id"] or 0)
            if user_id <= 0:
                return None
            dc_id = int(row["dc_id"] or 2)
            registered = _epoch_date(row["date"]) if "date" in row else "N/A"
            return AccountProfile(
                identifier=str(user_id),
                phone="N/A",
                username="N/A",
                full_name="N/A",
                user_id=user_id,
                dc_id=dc_id,
                registered=registered,
            )
    except (sqlite3.DatabaseError, OSError, ValueError):
        return None


def _session_dc_id(path: Path) -> int | None:
    try:
        with sqlite3.connect(f"file:{path}?mode=ro", uri=True) as conn:
            row = conn.execute("SELECT dc_id FROM sessions LIMIT 1").fetchone()
            if row and row[0]:
                return int(row[0])
    except (sqlite3.DatabaseError, OSError, ValueError):
        pass
    return None


def _registered_from_db(path: Path, user_id: int) -> str:
    try:
        with sqlite3.connect(f"file:{path}?mode=ro", uri=True) as conn:
            row = conn.execute(
                "SELECT date FROM users WHERE id = ? LIMIT 1", (user_id,)
            ).fetchone()
            if row:
                return _epoch_date(row[0])
    except (sqlite3.DatabaseError, OSError):
        pass
    return "N/A"


async def fetch_account_profile(
    session_path: Path,
    credentials: list[tuple[int, str]],
) -> tuple[AccountStatus, AccountProfile | None, str]:
    """Live profile fetch with offline fallbacks. Returns (status, profile, reason)."""
    if not session_path.exists() or not credentials:
        return "failed", None, "no_credentials"

    if _is_pyrogram_session(session_path):
        profile = _pyrogram_offline_profile(session_path)
        if profile is None:
            return "failed", None, "structural"
        return "invalid", profile, "pyrogram_offline"

    try:
        from telethon import TelegramClient  # type: ignore[import-untyped]
        from telethon.errors import (  # type: ignore[import-untyped]
            AuthKeyDuplicatedError,
            AuthKeyError,
            AuthKeyUnregisteredError,
            PhoneNumberBannedError,
            SessionRevokedError,
            UserDeactivatedBanError,
            UserDeactivatedError,
        )
        from telethon.tl.functions.account import (  # type: ignore[import-untyped]
            GetPasswordRequest,
        )
    except ModuleNotFoundError:
        return "failed", None, "telethon_missing"

    invalid_errors = (
        AuthKeyDuplicatedError,
        AuthKeyError,
        AuthKeyUnregisteredError,
        PhoneNumberBannedError,
        SessionRevokedError,
        UserDeactivatedBanError,
        UserDeactivatedError,
    )

    with tempfile.TemporaryDirectory(prefix="ftgc_account_txt_") as tmp:
        copied = Path(tmp) / "account.session"
        shutil.copy2(session_path, copied)
        session_stem = str(copied.with_suffix(""))

        last_error = "unknown"
        for api_id, api_hash in credentials:
            client = None
            try:
                from app.services.device_params import get_stable_device_params
                device_kwargs = get_stable_device_params(session_path)
                client = TelegramClient(
                    session_stem, api_id, api_hash, receive_updates=False, **device_kwargs
                )
                await client.connect()
                if not await client.is_user_authorized():
                    return "invalid", _fallback_profile(session_path), "unauthorized"

                me = await client.get_me()
                if me is None or not getattr(me, "id", None):
                    return "failed", None, "no_profile"

                two_fa: bool | None = None
                try:
                    password_state = await client(GetPasswordRequest())
                    two_fa = bool(getattr(password_state, "has_current_password", False))
                except Exception as exc:  # noqa: BLE001
                    LOGGER.debug("2FA probe failed for user %d: %s", me.id, exc)

                phone_digits = _clean_value(getattr(me, "phone", None), "")
                identifier = phone_digits or str(me.id)
                phone = f"+{phone_digits}" if phone_digits else "N/A"
                username_raw = _clean_value(getattr(me, "username", None), "")
                username = f"@{username_raw}" if username_raw else "N/A"
                full_name = (
                    " ".join(
                        part
                        for part in (
                            _clean_value(getattr(me, "first_name", None), ""),
                            _clean_value(getattr(me, "last_name", None), ""),
                        )
                        if part
                    )
                    or "N/A"
                )
                return (
                    "active",
                    AccountProfile(
                        identifier=identifier,
                        phone=phone,
                        username=username,
                        full_name=full_name,
                        user_id=int(me.id),
                        premium=bool(getattr(me, "premium", False)),
                        dc_id=_session_dc_id(session_path),
                        two_fa=two_fa,
                        registered=_registered_from_db(session_path, int(me.id)),
                    ),
                    "",
                )
            except invalid_errors as exc:
                return "invalid", _fallback_profile(session_path), type(exc).__name__
            except Exception as exc:  # noqa: BLE001
                last_error = type(exc).__name__
                LOGGER.debug(
                    "Account TXT credential failed for api_id=%d: %s", api_id, exc
                )
            finally:
                if client is not None:
                    with suppress(Exception):
                        await client.disconnect()
                    with suppress(Exception):
                        client.session.close()

    return "failed", None, last_error


def _sidecar_password(sidecars: list[Path]) -> str | None:
    for sidecar in sidecars:
        if sidecar.name.lower() in _SIDECAR_PASSWORD_NAMES:
            with suppress(OSError):
                content = sidecar.read_text(encoding="utf-8", errors="ignore")
                first = next(
                    (line.strip() for line in content.splitlines() if line.strip()),
                    None,
                )
                if first:
                    return first
    return None


def extract_zip_sessions_with_sidecars(
    zip_path: Path, target_dir: Path
) -> list[tuple[Path, list[Path]]]:
    """Extract every member of a ZIP (guarded) and pair each .session with its sidecars."""
    extracted: dict[Path, list[Path]] = {}
    with zipfile.ZipFile(zip_path, "r") as archive:
        members = archive.infolist()
        if len(members) > MAX_ZIP_MEMBERS:
            raise UnsafeArchiveError("zip_too_many_members")

        total_uncompressed = 0
        session_index = 0
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

            dest = target_dir / member_path
            dest.parent.mkdir(parents=True, exist_ok=True)
            if member_path.suffix.lower() == ".session":
                safe_name = f"session_{session_index}_{member_path.name}"
                session_index += 1
                dest = target_dir / safe_name
            with archive.open(info) as src, dest.open("wb") as dst:
                shutil.copyfileobj(src, dst)

        session_index = 0
        for info in members:
            member_path = Path(info.filename)
            if member_path.suffix.lower() != ".session":
                continue
            session_dir = member_path.parent
            sidecars = [
                target_dir / (session_dir / name)
                for name in _SIDECAR_PASSWORD_NAMES
                if (target_dir / (session_dir / name)).is_file()
            ]
            safe_name = f"session_{session_index}_{member_path.name}"
            session_index += 1
            extracted[target_dir / safe_name] = sidecars
    return sorted(extracted.items())


async def process_account_to_txt(
    input_path: Path,
    output_dir: Path,
    credentials: list[tuple[int, str]],
    *,
    original_name: str | None = None,
    progress: JobProgress | None = None,
    cancel_event: asyncio.Event | None = None,
) -> AccountTxtResult:
    temp_dir: tempfile.TemporaryDirectory[str] | None = None
    session_files: list[tuple[Path, list[Path]]] = []

    try:
        suffix = Path(original_name or input_path.name).suffix.lower()
        if suffix == ".zip":
            temp_dir = tempfile.TemporaryDirectory(prefix="ftgc_account_txt_zip_")
            try:
                session_files = await asyncio.to_thread(
                    extract_zip_sessions_with_sidecars,
                    input_path,
                    Path(temp_dir.name),
                )
            except zipfile.BadZipFile as exc:
                raise ValueError("bad_zip_file") from exc
        elif suffix == ".session":
            if original_name:
                temp_dir = tempfile.TemporaryDirectory(prefix="ftgc_account_txt_one_")
                copied = Path(temp_dir.name) / Path(original_name).name
                shutil.copy2(input_path, copied)
                session_files = [(copied, [])]
            else:
                session_files = [(input_path, [])]

        total = len(session_files)
        if progress is not None:
            progress.total = total

        active = 0
        invalid_converted = 0
        failed = 0
        rows: list[tuple[str, str, bool]] = []
        entries: list[AccountTxtEntry] = []
        phone_lines: list[str] = []
        status_lines: list[str] = []

        # Per-session probes hit the network (connect + up to 3-4 RPCs each).
        # Probing sequentially makes a 30-session zip take ~2-4 minutes. The
        # probes use distinct accounts but share the global api_credential
        # pairs, so concurrency is bounded like clean_chat: a small semaphore
        # plus batched asyncio.gather keeps order while cutting wall time.
        fetch_semaphore = asyncio.Semaphore(
            min(_PROBE_CONCURRENCY, len(session_files) or 1)
        )

        async def probe_session(index: int) -> tuple[int, AccountTxtEntry, tuple[str, str, bool] | None]:
            if cancel_event is not None and cancel_event.is_set():
                raise JobCancelled()
            session_file, sidecars = session_files[index]
            if not _is_structural_session(session_file):
                return (
                    index,
                    AccountTxtEntry(
                        profile=_placeholder_profile(session_file),
                        status="failed",
                        authorized=False,
                        reason="structural",
                    ),
                    None,
                )
            async with fetch_semaphore:
                status, profile, reason = await fetch_account_profile(
                    session_file, credentials
                )
            if status == "active" and profile is not None:
                profile = replace(profile, dc_id=_session_dc_id(session_file))
                entry = AccountTxtEntry(
                    profile=profile, status="active", authorized=True
                )
                row = (f"{profile.identifier}.txt", render_account_line(profile), True)
                return index, entry, row
            if status == "invalid" and profile is not None:
                sidecar_password = _sidecar_password(sidecars)
                profile = replace(
                    profile,
                    dc_id=_session_dc_id(session_file) or profile.dc_id,
                    two_fa=(
                        profile.two_fa
                        if profile.two_fa is not None
                        else bool(sidecar_password)
                        if sidecar_password is not None
                        else None
                    ),
                )
                entry = AccountTxtEntry(
                    profile=profile,
                    status="invalid",
                    authorized=False,
                    reason=reason,
                )
                row = (f"{profile.identifier}.txt", render_account_line(profile), False)
                return index, entry, row
            return (
                index,
                AccountTxtEntry(
                    profile=_placeholder_profile(session_file),
                    status="failed",
                    authorized=False,
                    reason=reason,
                ),
                None,
            )

        async def tracked_probe(
            index: int,
        ) -> tuple[int, AccountTxtEntry, tuple[str, str, bool] | None]:
            outcome = await probe_session(index)
            if progress is not None:
                progress.done += 1
            return outcome

        outcomes = await asyncio.gather(
            *(tracked_probe(index) for index in range(len(session_files)))
        )
        for index, entry, row in sorted(outcomes, key=lambda item: item[0]):
            if entry.status == "active":
                active += 1
            elif entry.status == "invalid":
                invalid_converted += 1
            else:
                failed += 1
            entries.append(entry)
            if row is not None:
                rows.append(row)
            phone = entry.profile.phone
            if phone and phone != "N/A":
                phone_lines.append(phone)
                if entry.status == "active":
                    status_lines.append(f"{phone} | ✅ active")
                elif entry.status == "invalid":
                    status_lines.append(f"{phone} | ⚠️ {entry.reason or 'invalid'}")
                else:
                    status_lines.append(f"{phone} | ❌ {entry.reason or 'failed'}")

        output_zip: Path | None = None
        phones_path: Path | None = None
        status_path: Path | None = None
        if rows or phone_lines:
            output_dir.mkdir(parents=True, exist_ok=True)
            if phone_lines:
                phones_path = output_dir / f"phones_{uuid4().hex[:10]}.txt"
                status_path = output_dir / f"phones_status_{uuid4().hex[:10]}.txt"
                phones_path.write_text("\n".join(phone_lines) + "\n", encoding="utf-8")
                status_path.write_text(
                    "\n".join(status_lines) + "\n", encoding="utf-8"
                )
            output_zip = output_dir / f"account_txt_{uuid4().hex[:10]}.zip"
            try:
                with zipfile.ZipFile(output_zip, "w", zipfile.ZIP_DEFLATED) as archive:
                    used: set[str] = set()
                    if phone_lines:
                        archive.writestr(
                            "phones.txt", "\n".join(phone_lines) + "\n"
                        )
                        used.add("phones.txt")
                    for index, (filename, line, is_active) in enumerate(rows, start=1):
                        arcname = filename
                        if arcname in used:
                            arcname = f"{Path(filename).stem}_{index}.txt"
                        used.add(arcname)
                        if not is_active:
                            arcname = f"Invalid/{arcname}"
                        archive.writestr(arcname, f"{line}\n")
            except OSError as exc:
                if exc.errno == errno.ENOSPC:
                    raise ValueError("storage_error") from exc
                raise

        return AccountTxtResult(
            total=total,
            active=active,
            invalid_converted=invalid_converted,
            failed=failed,
            output_zip_path=output_zip,
            phones_path=phones_path,
            status_path=status_path,
            entries=tuple(entries),
        )
    finally:
        if temp_dir is not None:
            temp_dir.cleanup()
