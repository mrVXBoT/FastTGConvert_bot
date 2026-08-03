from __future__ import annotations

import logging
import shutil
import sqlite3
import tempfile
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


@dataclass(frozen=True)
class ContactsCheckResult:
    checked: int
    ok: int
    error: int
    ok_zip_path: Path | None = None


async def check_session_contacts_live(
    session_path: Path,
    credentials: list[tuple[int, str]],
    proxy: tuple | None = None,
) -> tuple[bool | None, int]:
    """
    Connect via Telethon and fetch contacts count.
    Returns (is_ok, contacts_count) where is_ok is:
    - True if authorized and checked successfully
    - False if explicitly unauthorized / revoked / deactivated / invalid auth key / corrupt database
    - None if transient network/RPC error occurred across all credentials or Telethon missing
    """
    if not credentials or not session_path.exists():
        return None, 0

    try:
        # fmt: off
        from telethon import TelegramClient  # type: ignore[import-untyped]
        from telethon.errors import (  # type: ignore[import-untyped]
            ApiIdInvalidError,
            AuthKeyInvalidError,
            AuthKeyUnregisteredError,
            SessionRevokedError,
            UserDeactivatedError,
        )
        from telethon.tl.functions.contacts import (  # type: ignore[import-untyped]
            GetContactsRequest,
        )
        # fmt: on
    except ModuleNotFoundError:
        LOGGER.error("Telethon not installed for contacts check")
        return None, 0

    perm_auth_errors = (
        AuthKeyInvalidError,
        AuthKeyUnregisteredError,
        SessionRevokedError,
        UserDeactivatedError,
        ApiIdInvalidError,
        sqlite3.DatabaseError,
        sqlite3.OperationalError,
    )

    with tempfile.TemporaryDirectory(prefix="ftgc_cntread_") as tmp:
        tmp_session = Path(tmp) / "read.session"
        shutil.copy2(session_path, tmp_session)
        session_str = str(tmp_session.with_suffix(""))

        for api_id, api_hash in credentials:
            client = None
            try:
                client = TelegramClient(
                    session_str, api_id, api_hash, receive_updates=False, proxy=proxy
                )
                await client.connect()
                if not await client.is_user_authorized():
                    await client.disconnect()
                    return False, 0

                res = await client(GetContactsRequest(hash=0))
                contacts_count = len(getattr(res, "contacts", []))
                await client.disconnect()
                return True, contacts_count
            except perm_auth_errors as exc:
                LOGGER.debug(
                    "Contacts check permanent auth error with api_id=%d: %s",
                    api_id,
                    exc,
                )
                if client is not None:
                    with suppress(Exception):
                        await client.disconnect()
                return False, 0
            except Exception as exc:  # noqa: BLE001
                LOGGER.warning(
                    "Contacts check transient error with api_id=%d: %s", api_id, exc
                )
                if client is not None:
                    with suppress(Exception):
                        await client.disconnect()
                continue

    return None, 0


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


def extract_zip_sessions_safe(zip_path: Path, target_dir: Path) -> list[Path]:
    """
    Safely extract .session files from ZIP with Zip Slip & Zip Bomb guards.
    Uses error keys matching ARCHIVE_ERRORS in app/locales.py.
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


async def process_contacts_check(
    input_path: Path,
    output_dir: Path,
    credentials: list[tuple[int, str]] | None = None,
    proxy: tuple | None = None,
) -> ContactsCheckResult:
    """
    Process input file (.session or .zip) for contacts checking.
    Creates a unique contacts_ok_<uuid>.zip in output_dir if ok > 0.
    """
    session_files: list[Path] = []
    temp_dir: tempfile.TemporaryDirectory[str] | None = None

    try:
        if input_path.suffix.lower() == ".zip":
            temp_dir = tempfile.TemporaryDirectory(prefix="ftgc_cntzip_")
            tmp_path = Path(temp_dir.name)
            session_files = extract_zip_sessions_safe(input_path, tmp_path)
        elif input_path.suffix.lower() == ".session":
            session_files.append(input_path)

        checked = 0
        ok = 0
        error = 0
        ok_sessions: list[Path] = []

        for sess_file in session_files:
            checked += 1
            is_ok: bool = False
            if credentials:
                live_status, _ = await check_session_contacts_live(
                    sess_file, credentials, proxy=proxy
                )
                if live_status is not None:
                    is_ok = live_status
                else:
                    is_ok, _ = check_session_contacts_offline(sess_file)
            else:
                is_ok, _ = check_session_contacts_offline(sess_file)

            if is_ok:
                ok += 1
                ok_sessions.append(sess_file)
            else:
                error += 1

        ok_zip_path: Path | None = None
        if ok_sessions and ok > 0:
            output_dir.mkdir(parents=True, exist_ok=True)
            unique_zip_name = f"contacts_ok_{uuid4().hex}.zip"
            ok_zip_path = output_dir / unique_zip_name
            with zipfile.ZipFile(ok_zip_path, "w", zipfile.ZIP_DEFLATED) as zf:
                for sess in ok_sessions:
                    arcname = sess.name
                    if arcname.startswith("session_"):
                        parts = arcname.split("_", 2)
                        if len(parts) >= 3:
                            arcname = parts[2]
                    zf.write(sess, arcname=arcname)

        return ContactsCheckResult(
            checked=checked,
            ok=ok,
            error=error,
            ok_zip_path=ok_zip_path,
        )
    finally:
        if temp_dir is not None:
            temp_dir.cleanup()
