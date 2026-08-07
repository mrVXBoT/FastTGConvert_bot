from __future__ import annotations

import asyncio
import logging
import re
import shutil
import sqlite3
import tempfile
import zipfile
from contextlib import suppress
from dataclasses import dataclass
from pathlib import Path
from uuid import uuid4

import phonenumbers
from phonenumbers import geocoder

from app.services.contacts_checker import extract_zip_sessions_safe

LOGGER = logging.getLogger(__name__)


@dataclass(frozen=True)
class SplitOutput:
    path: Path
    filename: str
    label: str
    sessions: int
    flag: str | None = None


@dataclass(frozen=True)
class SessionSplitResult:
    total: int
    split: int
    failed: int
    outputs: tuple[SplitOutput, ...] = ()

    @property
    def groups(self) -> int:
        return len(self.outputs)


def _valid_session(path: Path) -> bool:
    try:
        with sqlite3.connect(f"file:{path}?mode=ro", uri=True) as connection:
            row = connection.execute("SELECT auth_key FROM sessions LIMIT 1").fetchone()
            auth_key = bytes(row[0]) if row and row[0] is not None else b""
            return len(auth_key) == 256 and any(auth_key)
    except (OSError, sqlite3.DatabaseError, TypeError, ValueError):
        return False


def _original_session_name(path: Path) -> str:
    name = path.name
    match = re.match(r"session_\d+_(.+\.session)$", name, flags=re.IGNORECASE)
    return match.group(1) if match else name


def _valid_phone(value: object) -> str | None:
    digits = re.sub(r"\D", "", str(value or ""))
    if not 10 <= len(digits) <= 15:
        return None
    phone = f"+{digits}"
    try:
        number = phonenumbers.parse(phone, None)
        return phone if phonenumbers.is_valid_number(number) else None
    except phonenumbers.NumberParseException:
        return None


def _phone_from_filename(path: Path) -> str | None:
    match = re.search(r"(?<!\d)(\d{10,15})(?!\d)", _original_session_name(path))
    return _valid_phone(match.group(1)) if match else None


def _phone_from_entities(path: Path) -> str | None:
    try:
        with sqlite3.connect(f"file:{path}?mode=ro", uri=True) as connection:
            connection.row_factory = sqlite3.Row
            table = connection.execute(
                "SELECT 1 FROM sqlite_master WHERE type='table' AND name='entities'"
            ).fetchone()
            if table:
                rows = connection.execute(
                    "SELECT phone FROM entities WHERE phone IS NOT NULL AND phone != ''"
                ).fetchall()
                for row in rows:
                    phone = _valid_phone(row["phone"])
                    if phone:
                        return phone
    except (OSError, sqlite3.DatabaseError, TypeError, ValueError):
        pass
    return None


async def _live_probe(
    session_path: Path,
    credentials: list[tuple[int, str]],
) -> tuple[bool, str | None]:
    """Fast live authorization probe for splitting.

    One ``connect`` + ``get_me`` per session with the 2FA probe skipped and
    Telethon retries/timeouts bounded, so dead or unreachable sessions fail in
    seconds instead of hanging on Telethon's default retry loops.  Returns
    ``(authorized, live_phone)``.
    """
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
    except ModuleNotFoundError:
        return False, None

    invalid_errors = (
        AuthKeyDuplicatedError,
        AuthKeyError,
        AuthKeyUnregisteredError,
        PhoneNumberBannedError,
        SessionRevokedError,
        UserDeactivatedBanError,
        UserDeactivatedError,
    )

    with tempfile.TemporaryDirectory(prefix="ftgc_split_probe_") as tmp:
        copied = Path(tmp) / "account.session"
        shutil.copy2(session_path, copied)
        session_stem = str(copied.with_suffix(""))

        for api_id, api_hash in credentials:
            client = None
            try:
                client = TelegramClient(
                    session_stem,
                    api_id,
                    api_hash,
                    receive_updates=False,
                    connection_retries=1,
                    request_retries=1,
                    retry_delay=0.25,
                    timeout=10,
                    flood_sleep_threshold=0,
                )
                await client.connect()
                if not await client.is_user_authorized():
                    return False, None
                me = await client.get_me()
                if me is None or not getattr(me, "id", None):
                    return False, None
                return True, _valid_phone(getattr(me, "phone", None))
            except invalid_errors:
                return False, None
            except Exception as exc:  # noqa: BLE001
                LOGGER.debug(
                    "Split live probe failed for api_id=%d on %s: %s",
                    api_id,
                    session_path.name,
                    exc,
                )
            finally:
                if client is not None:
                    with suppress(Exception):
                        await client.disconnect()
                    with suppress(Exception):
                        client.session.close()

    return False, None


async def _check_session(
    session_path: Path,
    credentials: list[tuple[int, str]] | None,
) -> tuple[bool, str | None]:
    """Return ``(splittable, resolved_phone)`` for one session.

    When *credentials* are provided the session is verified live against
    Telegram with a single fast API probe; only genuinely authorized sessions
    count as splittable and the real phone from the API profile is preferred
    over filename guessing.  Without credentials a pure offline structural
    check is used and the result must be treated as unverified.
    """
    if not credentials:
        if not _valid_session(session_path):
            return False, None
        phone = _phone_from_filename(session_path) or _phone_from_entities(
            session_path
        )
        return True, phone
    try:
        authorized, live_phone = await _live_probe(session_path, credentials)
    except Exception:  # noqa: BLE001
        return False, None
    if not authorized:
        return False, None
    phone = live_phone
    if phone is None:
        phone = _phone_from_filename(session_path) or _phone_from_entities(
            session_path
        )
    return True, phone


def country_for_phone(phone: str | None) -> str:
    if not phone:
        return "Unknown"
    try:
        number = phonenumbers.parse(phone, None)
        if not phonenumbers.is_valid_number(number):
            return "Unknown"
        description = geocoder.description_for_number(number, "en")
        if description:
            return description
        region = phonenumbers.region_code_for_number(number)
        return region or "Unknown"
    except phonenumbers.NumberParseException:
        return "Unknown"


def flag_for_phone(phone: str | None) -> str | None:
    if not phone:
        return None
    try:
        number = phonenumbers.parse(phone, None)
        if not phonenumbers.is_valid_number(number):
            return None
        region = phonenumbers.region_code_for_number(number)
        if not region or len(region) != 2 or not region.isalpha():
            return None
        return "".join(
            chr(0x1F1E6 + ord(char) - ord("A")) for char in region.upper()
        )
    except phonenumbers.NumberParseException:
        return None


def _safe_label(label: str) -> str:
    cleaned = re.sub(r"[^0-9A-Za-z_-]+", "_", label).strip("_")
    return cleaned or "Unknown"


def _write_session_zip(
    output_dir: Path,
    sessions: list[Path],
    *,
    display_name: str,
    label: str,
    flag: str | None = None,
) -> SplitOutput:
    output_dir.mkdir(parents=True, exist_ok=True)
    path = output_dir / f"split_{uuid4().hex[:10]}.zip"
    with zipfile.ZipFile(path, "w", zipfile.ZIP_DEFLATED) as archive:
        used: set[str] = set()
        for index, session in enumerate(sessions, start=1):
            name = _original_session_name(session)
            if name in used:
                name = f"{Path(name).stem}_{index}.session"
            used.add(name)
            archive.write(session, arcname=name)
    return SplitOutput(path, display_name, label, len(sessions), flag)


def _collect_sessions(
    input_path: Path,
    work_dir: Path,
    *,
    original_name: str | None,
) -> list[Path]:
    suffix = Path(original_name or input_path.name).suffix.lower()
    if suffix == ".zip":
        return extract_zip_sessions_safe(input_path, work_dir)
    if suffix == ".session":
        destination = work_dir / Path(original_name or input_path.name).name
        shutil.copy2(input_path, destination)
        return [destination]
    return []


async def inspect_session_split(
    input_path: Path, *, original_name: str | None = None
) -> int:
    with tempfile.TemporaryDirectory(prefix="ftgc_split_inspect_") as temporary:
        sessions = _collect_sessions(
            input_path, Path(temporary), original_name=original_name
        )
        return len(sessions)


async def process_session_split(
    input_path: Path,
    mode: str,
    output_dir: Path,
    credentials: list[tuple[int, str]] | None = None,
    *,
    quantity: int | None = None,
    original_name: str | None = None,
    concurrency: int = 10,
) -> SessionSplitResult:
    if mode not in {"country", "quantity"}:
        raise ValueError("invalid_split_type")
    if mode == "quantity" and (quantity is None or quantity <= 0):
        raise ValueError("invalid_quantity")
    if concurrency < 1:
        raise ValueError("invalid_concurrency")

    with tempfile.TemporaryDirectory(prefix="ftgc_session_split_") as temporary:
        sessions = _collect_sessions(
            input_path, Path(temporary), original_name=original_name
        )
        total = len(sessions)

        semaphore = asyncio.Semaphore(concurrency)

        async def check(session: Path) -> tuple[Path, bool, str | None]:
            async with semaphore:
                authorized, phone = await _check_session(
                    session, credentials or None
                )
                return session, authorized, phone

        checked = await asyncio.gather(*(check(session) for session in sessions))
        valid: list[Path] = []
        phone_by_session: dict[Path, str | None] = {}
        failed = 0
        for session, authorized, phone in checked:
            if authorized:
                valid.append(session)
                phone_by_session[session] = phone
            else:
                failed += 1
        outputs: list[SplitOutput] = []

        if mode == "quantity":
            assert quantity is not None
            for start in range(0, len(valid), quantity):
                group = valid[start : start + quantity]
                part_number = len(outputs) + 1
                filename = f"Part{part_number:03d}_{len(group)}.zip"
                outputs.append(
                    _write_session_zip(
                        output_dir,
                        group,
                        display_name=filename,
                        label=f"Part {part_number}",
                    )
                )
        else:
            country_groups: dict[str, list[Path]] = {}
            country_flags: dict[str, str | None] = {}
            for session in valid:
                phone = phone_by_session.get(session)
                country = country_for_phone(phone)
                country_groups.setdefault(country, []).append(session)
                if country not in country_flags:
                    country_flags[country] = flag_for_phone(phone)

            for country in sorted(country_groups):
                group = country_groups[country]
                filename = f"{_safe_label(country)}_{len(group)}.zip"
                outputs.append(
                    _write_session_zip(
                        output_dir,
                        group,
                        display_name=filename,
                        label=country,
                        flag=country_flags.get(country),
                    )
                )

        return SessionSplitResult(
            total=total,
            split=len(valid),
            failed=failed,
            outputs=tuple(outputs),
        )
