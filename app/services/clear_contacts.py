from __future__ import annotations

import logging
import shutil
import tempfile
import zipfile
from contextlib import suppress
from dataclasses import dataclass
from pathlib import Path
from uuid import uuid4

from app.services.contacts_checker import extract_zip_sessions_safe
from app.services.file_merge import _is_valid_sqlite_session
from app.services.session_to_tdata import _ensure_opentele_patched

LOGGER = logging.getLogger(__name__)


@dataclass(frozen=True)
class ClearContactsResult:
    total: int
    cleared: int
    failed: int
    output_path: Path | None = None
    is_zip: bool = False


async def clear_session_contacts(
    session_file: Path,
    credentials: list[tuple[int, str]],
) -> bool:
    if not credentials or not session_file.exists():
        return False

    try:
        from telethon import TelegramClient, functions  # type: ignore[import-untyped]
    except ModuleNotFoundError:
        LOGGER.error("Telethon not installed for clear contacts")
        return False

    with tempfile.TemporaryDirectory(prefix="ftgc_cntclear_") as tmp:
        run_sess = Path(tmp) / "account.session"
        shutil.copy2(session_file, run_sess)
        stem = str(run_sess.with_suffix(""))

        for api_id, api_hash in credentials:
            client = None
            cleared = False
            try:
                client = TelegramClient(stem, api_id, api_hash, receive_updates=False)
                await client.connect()
                if not await client.is_user_authorized():
                    continue

                res = await client(functions.contacts.GetContactsRequest(hash=0))
                contacts_list = getattr(res, "contacts", [])
                if contacts_list:
                    contact_ids = [
                        getattr(c, "user_id", getattr(c, "id", None))
                        for c in contacts_list
                    ]
                    users_by_id = {
                        getattr(user, "id", None): user
                        for user in getattr(res, "users", [])
                    }
                    delete_targets = [
                        users_by_id.get(user_id, user_id)
                        for user_id in contact_ids
                        if user_id is not None
                    ]
                    if delete_targets:
                        await client(
                            functions.contacts.DeleteContactsRequest(id=delete_targets)
                        )

                # deleteContacts removes Telegram users from the contact list;
                # resetSaved separately removes saved phone contacts that have
                # no associated Telegram account.
                await client(functions.contacts.ResetSavedRequest())
                cleared = True
            except Exception as exc:  # noqa: BLE001
                LOGGER.debug(
                    "Clear contacts attempt failed with api_id=%d: %s", api_id, exc
                )
            finally:
                if client is not None:
                    with suppress(Exception):
                        await client.disconnect()

            if cleared:
                shutil.copy2(run_sess, session_file)
                return True

    return False


async def process_clear_contacts(
    input_path: Path,
    output_dir: Path,
    credentials: list[tuple[int, str]],
    *,
    original_name: str | None = None,
) -> ClearContactsResult:
    _ensure_opentele_patched()
    output_dir.mkdir(parents=True, exist_ok=True)
    temp_dir: tempfile.TemporaryDirectory[str] | None = None
    session_files: list[Path] = []

    try:
        suffix = Path(original_name or input_path.name).suffix.lower()
        if suffix == ".zip":
            temp_dir = tempfile.TemporaryDirectory(prefix="ftgc_cntclr_zip_")
            session_files = extract_zip_sessions_safe(input_path, Path(temp_dir.name))
        elif suffix == ".session":
            if original_name:
                temp_dir = tempfile.TemporaryDirectory(prefix="ftgc_cntclr_one_")
                copied = Path(temp_dir.name) / Path(original_name).name
                shutil.copy2(input_path, copied)
                session_files = [copied]
            else:
                session_files = [input_path]

        total = len(session_files)
        success_files: list[Path] = []
        failed = 0

        for sess_file in session_files:
            if not _is_valid_sqlite_session(sess_file):
                failed += 1
                continue

            cleared = await clear_session_contacts(sess_file, credentials)
            if cleared:
                success_files.append(sess_file)
            else:
                failed += 1

        cleared_count = len(success_files)
        output_path: Path | None = None
        is_zip = False

        if cleared_count > 0:
            if cleared_count == 1 and total == 1:
                output_path = (
                    output_dir / f"Contacts_Cleared_1_{uuid4().hex[:6]}.session"
                )
                shutil.copy2(success_files[0], output_path)
            else:
                is_zip = True
                output_path = (
                    output_dir
                    / f"Contacts_Cleared_{cleared_count}_{uuid4().hex[:6]}.zip"
                )
                with zipfile.ZipFile(output_path, "w", zipfile.ZIP_DEFLATED) as archive:
                    used_names: set[str] = set()
                    for idx, sfile in enumerate(success_files, start=1):
                        arcname = sfile.name
                        if arcname in used_names:
                            arcname = f"{sfile.stem}_{idx}.session"
                        used_names.add(arcname)
                        archive.write(sfile, arcname=arcname)

        return ClearContactsResult(
            total=total,
            cleared=cleared_count,
            failed=failed,
            output_path=output_path,
            is_zip=is_zip,
        )
    finally:
        if temp_dir is not None:
            temp_dir.cleanup()
