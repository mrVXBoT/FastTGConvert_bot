from __future__ import annotations

import re
import shutil
import sqlite3
import tempfile
import zipfile
from dataclasses import dataclass
from pathlib import Path
from uuid import uuid4

import phonenumbers
from phonenumbers import geocoder

from app.services.account_to_txt import fetch_account_profile
from app.services.contacts_checker import extract_zip_sessions_safe


@dataclass(frozen=True)
class SplitOutput:
    path: Path
    filename: str
    label: str
    sessions: int


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


async def _resolve_phone(
    session_path: Path, credentials: list[tuple[int, str]]
) -> str | None:
    phone = _phone_from_filename(session_path)
    if phone:
        return phone

    if credentials:
        _status, profile = await fetch_account_profile(session_path, credentials)
        if profile is not None and profile.phone != "N/A":
            profile_phone = _valid_phone(profile.phone)
            if profile_phone:
                return profile_phone

    return _phone_from_entities(session_path)


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


def _safe_label(label: str) -> str:
    cleaned = re.sub(r"[^0-9A-Za-z_-]+", "_", label).strip("_")
    return cleaned or "Unknown"


def _write_session_zip(
    output_dir: Path,
    sessions: list[Path],
    *,
    display_name: str,
    label: str,
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
    return SplitOutput(path, display_name, label, len(sessions))


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
) -> SessionSplitResult:
    if mode not in {"country", "quantity"}:
        raise ValueError("invalid_split_type")
    if mode == "quantity" and (quantity is None or quantity <= 0):
        raise ValueError("invalid_quantity")

    with tempfile.TemporaryDirectory(prefix="ftgc_session_split_") as temporary:
        sessions = _collect_sessions(
            input_path, Path(temporary), original_name=original_name
        )
        total = len(sessions)
        valid = [session for session in sessions if _valid_session(session)]
        failed = total - len(valid)
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
            for session in valid:
                phone = await _resolve_phone(session, credentials or [])
                country = country_for_phone(phone)
                country_groups.setdefault(country, []).append(session)

            for country in sorted(country_groups):
                group = country_groups[country]
                filename = f"{_safe_label(country)}_{len(group)}.zip"
                outputs.append(
                    _write_session_zip(
                        output_dir,
                        group,
                        display_name=filename,
                        label=country,
                    )
                )

        return SessionSplitResult(
            total=total,
            split=len(valid),
            failed=failed,
            outputs=tuple(outputs),
        )
