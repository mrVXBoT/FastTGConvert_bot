from __future__ import annotations

import logging
import re
import shutil
import sqlite3
import tempfile
import zipfile
from contextlib import suppress
from dataclasses import dataclass
from pathlib import Path
from typing import Literal
from uuid import uuid4

from app.services.contacts_checker import extract_zip_sessions_safe

LOGGER = logging.getLogger(__name__)

AccountStatus = Literal["active", "invalid", "failed"]


@dataclass(frozen=True)
class AccountProfile:
    identifier: str
    phone: str
    username: str
    full_name: str
    user_id: int
    premium: bool = False


@dataclass(frozen=True)
class AccountTxtResult:
    total: int
    active: int
    invalid_converted: int
    failed: int
    output_zip_path: Path | None = None

    @property
    def converted(self) -> int:
        return self.active + self.invalid_converted


def _clean_value(value: object, fallback: str = "N/A") -> str:
    cleaned = (
        str(value or "").replace("|", " ").replace("\r", " ").replace("\n", " ").strip()
    )
    return cleaned or fallback


def render_account_line(profile: AccountProfile) -> str:
    return "|".join(
        (
            _clean_value(profile.identifier),
            _clean_value(profile.phone),
            _clean_value(profile.username),
            _clean_value(profile.full_name),
            str(profile.user_id),
        )
    )


def _original_stem(path: Path) -> str:
    stem = path.stem
    if stem.startswith("session_"):
        parts = stem.split("_", 2)
        if len(parts) == 3:
            stem = parts[2]
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


def _is_structural_session(path: Path) -> bool:
    try:
        with sqlite3.connect(f"file:{path}?mode=ro", uri=True) as conn:
            row = conn.execute("SELECT auth_key FROM sessions LIMIT 1").fetchone()
            return bool(row and row[0] and len(row[0]) == 256)
    except (sqlite3.DatabaseError, OSError):
        return False


async def fetch_account_profile(
    session_path: Path,
    credentials: list[tuple[int, str]],
) -> tuple[AccountStatus, AccountProfile | None]:
    if not session_path.exists() or not credentials:
        return "failed", None

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
        return "failed", None

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

        for api_id, api_hash in credentials:
            client = None
            try:
                client = TelegramClient(
                    session_stem, api_id, api_hash, receive_updates=False
                )
                await client.connect()
                if not await client.is_user_authorized():
                    return "invalid", _fallback_profile(session_path)

                me = await client.get_me()
                if me is None or not getattr(me, "id", None):
                    return "failed", None

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
                    ),
                )
            except invalid_errors:
                return "invalid", _fallback_profile(session_path)
            except Exception as exc:  # noqa: BLE001
                LOGGER.debug(
                    "Account TXT credential failed for api_id=%d: %s", api_id, exc
                )
            finally:
                if client is not None:
                    with suppress(Exception):
                        await client.disconnect()

    return "failed", None


async def process_account_to_txt(
    input_path: Path,
    output_dir: Path,
    credentials: list[tuple[int, str]],
    *,
    original_name: str | None = None,
) -> AccountTxtResult:
    temp_dir: tempfile.TemporaryDirectory[str] | None = None
    session_files: list[Path] = []

    try:
        suffix = Path(original_name or input_path.name).suffix.lower()
        if suffix == ".zip":
            temp_dir = tempfile.TemporaryDirectory(prefix="ftgc_account_txt_zip_")
            session_files = extract_zip_sessions_safe(input_path, Path(temp_dir.name))
        elif suffix == ".session":
            if original_name:
                temp_dir = tempfile.TemporaryDirectory(prefix="ftgc_account_txt_one_")
                copied = Path(temp_dir.name) / Path(original_name).name
                shutil.copy2(input_path, copied)
                session_files = [copied]
            else:
                session_files = [input_path]

        total = len(session_files)
        active = 0
        invalid_converted = 0
        failed = 0
        rows: list[tuple[str, str]] = []

        for session_file in session_files:
            if not _is_structural_session(session_file):
                failed += 1
                continue

            status, profile = await fetch_account_profile(session_file, credentials)
            if status == "active" and profile is not None:
                active += 1
            elif status == "invalid" and profile is not None:
                invalid_converted += 1
            else:
                failed += 1
                continue

            filename = f"{profile.identifier}.txt"
            rows.append((filename, render_account_line(profile)))

        output_zip: Path | None = None
        if rows:
            output_dir.mkdir(parents=True, exist_ok=True)
            output_zip = output_dir / f"account_txt_{uuid4().hex[:10]}.zip"
            with zipfile.ZipFile(output_zip, "w", zipfile.ZIP_DEFLATED) as archive:
                used: set[str] = set()
                for index, (filename, line) in enumerate(rows, start=1):
                    arcname = filename
                    if arcname in used:
                        arcname = f"{Path(filename).stem}_{index}.txt"
                    used.add(arcname)
                    archive.writestr(arcname, f"{line}\n")

        return AccountTxtResult(
            total=total,
            active=active,
            invalid_converted=invalid_converted,
            failed=failed,
            output_zip_path=output_zip,
        )
    finally:
        if temp_dir is not None:
            temp_dir.cleanup()
