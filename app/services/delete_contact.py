from __future__ import annotations

import asyncio
import logging
import shutil
import tempfile
import zipfile
from contextlib import suppress
from dataclasses import asdict, dataclass
from pathlib import Path
from uuid import uuid4

from app.services.contacts_checker import extract_zip_sessions_safe
from app.services.file_merge import (
    _is_valid_sqlite_session,
    extract_account_identifier,
)
from app.services.session_to_tdata import _ensure_opentele_patched

LOGGER = logging.getLogger(__name__)


@dataclass(frozen=True)
class ContactItem:
    user_id: int
    first_name: str
    last_name: str
    phone: str

    def to_dict(self) -> dict:
        return asdict(self)


@dataclass(frozen=True)
class DeleteContactsResult:
    total: int
    deleted: int
    failed: int
    output_path: Path | None = None
    is_zip: bool = False


def _contacts_from_response(response: object) -> list[ContactItem]:
    users_dict = {
        getattr(user, "id", None): user
        for user in getattr(response, "users", [])
        if getattr(user, "id", None)
    }
    items: list[ContactItem] = []
    for contact in getattr(response, "contacts", []):
        user_id = getattr(contact, "user_id", getattr(contact, "id", None))
        user = users_dict.get(user_id)
        if not isinstance(user_id, int) or user is None:
            continue
        items.append(
            ContactItem(
                user_id=user_id,
                first_name=str(getattr(user, "first_name", "") or ""),
                last_name=str(getattr(user, "last_name", "") or ""),
                phone=str(getattr(user, "phone", "") or ""),
            )
        )
    return items


async def fetch_session_contacts(
    session_file: Path,
    credentials: list[tuple[int, str]],
) -> list[ContactItem]:
    if not credentials or not session_file.exists():
        return []

    try:
        from telethon import TelegramClient, functions  # type: ignore[import-untyped]
    except ModuleNotFoundError:
        LOGGER.error("Telethon not installed for fetch contacts")
        return []

    with tempfile.TemporaryDirectory(prefix="ftgc_fetch_cnt_") as tmp:
        run_sess = Path(tmp) / "account.session"
        shutil.copy2(session_file, run_sess)
        stem = str(run_sess.with_suffix(""))

        for api_id, api_hash in credentials:
            client = None
            try:
                from app.services.device_params import get_stable_device_params
                device_kwargs = get_stable_device_params(session_file)
                client = TelegramClient(stem, api_id, api_hash, receive_updates=False, **device_kwargs)
                await client.connect()
                if not await client.is_user_authorized():
                    # Dead auth key: unauthorized under any api_id.
                    break

                res = await client(functions.contacts.GetContactsRequest(hash=0))
                return _contacts_from_response(res)
            except Exception as exc:  # noqa: BLE001
                LOGGER.warning("Fetch contacts failed with api_id=%d: %s", api_id, exc)
            finally:
                if client is not None:
                    with suppress(Exception):
                        await client.disconnect()

    return []


async def fetch_input_contacts(
    input_path: Path,
    credentials: list[tuple[int, str]],
    *,
    original_name: str | None = None,
) -> list[ContactItem]:
    """Return the de-duplicated union of contacts from session or ZIP input."""
    temp_dir: tempfile.TemporaryDirectory[str] | None = None
    session_files: list[Path] = []
    try:
        suffix = Path(original_name or input_path.name).suffix.lower()
        if suffix == ".zip":
            temp_dir = tempfile.TemporaryDirectory(prefix="ftgc_fetch_cnt_zip_")
            session_files = await asyncio.to_thread(
                extract_zip_sessions_safe, input_path, Path(temp_dir.name)
            )
        elif suffix == ".session":
            session_files = [input_path]

        contacts_by_id: dict[int, ContactItem] = {}
        for session_file in session_files:
            if not _is_valid_sqlite_session(session_file):
                continue
            for item in await fetch_session_contacts(session_file, credentials):
                current = contacts_by_id.get(item.user_id)
                if current is None:
                    contacts_by_id[item.user_id] = item
                else:
                    contacts_by_id[item.user_id] = ContactItem(
                        user_id=item.user_id,
                        first_name=current.first_name or item.first_name,
                        last_name=current.last_name or item.last_name,
                        phone=current.phone or item.phone,
                    )

        return sorted(
            contacts_by_id.values(),
            key=lambda item: (
                item.first_name.casefold(),
                item.last_name.casefold(),
                item.user_id,
            ),
        )
    finally:
        if temp_dir is not None:
            temp_dir.cleanup()


async def delete_session_contacts(
    session_file: Path,
    credentials: list[tuple[int, str]],
    target_user_ids: list[int],
) -> bool:
    selected_ids = {user_id for user_id in target_user_ids if user_id > 0}
    if not credentials or not session_file.exists() or not selected_ids:
        return False

    try:
        from telethon import TelegramClient, functions  # type: ignore[import-untyped]
    except ModuleNotFoundError:
        LOGGER.error("Telethon not installed for delete contacts")
        return False

    with tempfile.TemporaryDirectory(prefix="ftgc_del_cnt_") as tmp:
        run_sess = Path(tmp) / "account.session"
        shutil.copy2(session_file, run_sess)
        stem = str(run_sess.with_suffix(""))

        for api_id, api_hash in credentials:
            client = None
            deleted = False
            try:
                from app.services.device_params import get_stable_device_params
                device_kwargs = get_stable_device_params(session_file)
                client = TelegramClient(stem, api_id, api_hash, receive_updates=False, **device_kwargs)
                await client.connect()
                if not await client.is_user_authorized():
                    # Dead auth key: unauthorized under any api_id.
                    break

                response = await client(functions.contacts.GetContactsRequest(hash=0))
                contacts = _contacts_from_response(response)
                users_by_id = {
                    getattr(user, "id", None): user
                    for user in getattr(response, "users", [])
                }
                delete_targets = [
                    users_by_id.get(contact.user_id, contact.user_id)
                    for contact in contacts
                    if contact.user_id in selected_ids
                ]
                if delete_targets:
                    await client(
                        functions.contacts.DeleteContactsRequest(id=delete_targets)
                    )
                deleted = True
            except Exception as exc:  # noqa: BLE001
                LOGGER.warning("Delete contacts failed with api_id=%d: %s", api_id, exc)
            finally:
                if client is not None:
                    with suppress(Exception):
                        await client.disconnect()

            if deleted:
                shutil.copy2(run_sess, session_file)
                return True

    return False


async def process_delete_contacts(
    input_path: Path,
    output_dir: Path,
    credentials: list[tuple[int, str]],
    target_user_ids: list[int],
    *,
    original_name: str | None = None,
) -> DeleteContactsResult:
    selected_ids = sorted({user_id for user_id in target_user_ids if user_id > 0})
    if not selected_ids:
        raise ValueError("no_contacts_selected")
    _ensure_opentele_patched()
    output_dir.mkdir(parents=True, exist_ok=True)
    temp_dir: tempfile.TemporaryDirectory[str] | None = None
    session_files: list[Path] = []

    try:
        suffix = Path(original_name or input_path.name).suffix.lower()
        if suffix == ".zip":
            temp_dir = tempfile.TemporaryDirectory(prefix="ftgc_delcnt_zip_")
            session_files = await asyncio.to_thread(
                extract_zip_sessions_safe, input_path, Path(temp_dir.name)
            )
        elif suffix == ".session":
            if original_name:
                temp_dir = tempfile.TemporaryDirectory(prefix="ftgc_delcnt_one_")
                copied = Path(temp_dir.name) / Path(original_name).name
                shutil.copy2(input_path, copied)
                session_files = [copied]
            else:
                session_files = [input_path]

        total = len(session_files)
        success_files: list[Path] = []
        failed = 0

        LOGGER.info(
            "Starting Delete Contacts (Target User IDs: %s) for %d session(s)...",
            selected_ids,
            total,
        )

        for sess_file in session_files:
            identifier, uid, phone = extract_account_identifier(sess_file)
            if not _is_valid_sqlite_session(sess_file):
                failed += 1
                LOGGER.warning(
                    "Delete Contacts: Account=%s | Phone=%s | UserID=%s → FAILED (invalid session)",
                    identifier,
                    f"+{phone}" if phone else "N/A",
                    uid or "N/A",
                )
                continue

            deleted = await delete_session_contacts(
                sess_file, credentials, selected_ids
            )
            if deleted:
                success_files.append(sess_file)
                LOGGER.info(
                    "Delete Contacts: Account=%s | Phone=%s | UserID=%s → SUCCESS",
                    identifier,
                    f"+{phone}" if phone else "N/A",
                    uid or "N/A",
                )
            else:
                failed += 1
                LOGGER.warning(
                    "Delete Contacts: Account=%s | Phone=%s | UserID=%s → FAILED",
                    identifier,
                    f"+{phone}" if phone else "N/A",
                    uid or "N/A",
                )

        deleted_count = len(success_files)
        output_path: Path | None = None
        is_zip = False

        if deleted_count > 0:
            if deleted_count == 1 and total == 1:
                output_path = (
                    output_dir / f"Delete_Contacts_1_{uuid4().hex[:6]}.session"
                )
                shutil.copy2(success_files[0], output_path)
            else:
                is_zip = True
                output_path = (
                    output_dir
                    / f"Delete_Contacts_{deleted_count}_{uuid4().hex[:6]}.zip"
                )
                with zipfile.ZipFile(output_path, "w", zipfile.ZIP_DEFLATED) as archive:
                    used_names: set[str] = set()
                    for idx, sfile in enumerate(success_files, start=1):
                        arcname = sfile.name
                        if arcname in used_names:
                            arcname = f"{sfile.stem}_{idx}.session"
                        used_names.add(arcname)
                        archive.write(sfile, arcname=arcname)

        LOGGER.info(
            "Delete Contacts Summary: Total=%d | Deleted=%d | Failed=%d | Output=%s",
            total,
            deleted_count,
            failed,
            output_path.name if output_path else "None",
        )

        return DeleteContactsResult(
            total=total,
            deleted=deleted_count,
            failed=failed,
            output_path=output_path,
            is_zip=is_zip,
        )
    finally:
        if temp_dir is not None:
            temp_dir.cleanup()
