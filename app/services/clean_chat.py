from __future__ import annotations

import logging
import shutil
import tempfile
import zipfile
from collections.abc import Collection
from contextlib import suppress
from dataclasses import dataclass
from pathlib import Path
from uuid import uuid4

from app.services.contacts_checker import extract_zip_sessions_safe
from app.services.file_merge import _is_valid_sqlite_session
from app.services.session_to_tdata import _ensure_opentele_patched

LOGGER = logging.getLogger(__name__)
CLEAN_CHAT_CATEGORIES = frozenset({"dms", "bots", "groups", "channels"})


def normalize_clean_chat_selection(
    selection: str | Collection[str],
) -> frozenset[str]:
    if isinstance(selection, str):
        selected = (
            CLEAN_CHAT_CATEGORIES if selection == "all" else frozenset({selection})
        )
    else:
        selected = frozenset(selection)

    if not selected or not selected <= CLEAN_CHAT_CATEGORIES:
        raise ValueError("invalid_clean_chat_selection")
    return selected


@dataclass(frozen=True)
class CleanChatResult:
    total: int
    cleaned: int
    failed: int
    output_path: Path | None = None
    is_zip: bool = False


async def clean_session_chats(
    session_file: Path,
    credentials: list[tuple[int, str]],
    mode: str | Collection[str] = "all",
) -> bool:
    """
    Connect via Telethon and clean chats for a session account according to mode.
    Categories can contain any combination of dms, bots, groups and channels.
    The legacy string all selects every category.
    """
    selected_categories = normalize_clean_chat_selection(mode)
    if not credentials or not session_file.exists():
        return False

    try:
        from telethon import TelegramClient  # type: ignore[import-untyped]
    except ModuleNotFoundError:
        LOGGER.error("Telethon not installed for clean chat")
        return False

    with tempfile.TemporaryDirectory(prefix="ftgc_clean_chat_") as tmp:
        run_sess = Path(tmp) / "account.session"
        shutil.copy2(session_file, run_sess)
        stem = str(run_sess.with_suffix(""))

        for api_id, api_hash in credentials:
            client = None
            cleaned = False
            try:
                client = TelegramClient(stem, api_id, api_hash, receive_updates=False)
                await client.connect()
                if not await client.is_user_authorized():
                    continue

                failed_dialogs = 0
                async for dialog in client.iter_dialogs():
                    is_user = getattr(dialog, "is_user", False)
                    is_group = getattr(dialog, "is_group", False)
                    is_channel = getattr(dialog, "is_channel", False)
                    is_broadcast = bool(
                        getattr(getattr(dialog, "entity", None), "broadcast", False)
                    )
                    is_bot = is_user and bool(
                        getattr(getattr(dialog, "entity", None), "bot", False)
                    )

                    category: str | None = None
                    if is_user:
                        category = "bots" if is_bot else "dms"
                    elif is_channel and is_broadcast:
                        category = "channels"
                    elif is_group or is_channel:
                        category = "groups"

                    should_clean = category in selected_categories

                    if should_clean:
                        entity = dialog.entity
                        try:
                            # For users this removes the dialog only for the current
                            # account. For groups/channels Telethon leaves or
                            # unsubscribes, which is the intended Clean Chat action.
                            await client.delete_dialog(entity, revoke=False)
                        except Exception as exc:  # noqa: BLE001
                            failed_dialogs += 1
                            LOGGER.warning(
                                "Failed cleaning dialog %s: %s",
                                getattr(entity, "id", entity),
                                exc,
                            )

                cleaned = failed_dialogs == 0
            except Exception as exc:  # noqa: BLE001
                LOGGER.warning(
                    "Clean chat attempt failed with api_id=%d: %s", api_id, exc
                )
            finally:
                if client is not None:
                    with suppress(Exception):
                        await client.disconnect()

            if cleaned:
                shutil.copy2(run_sess, session_file)
                return True

    return False


async def process_clean_chat(
    input_path: Path,
    output_dir: Path,
    mode: str | Collection[str],
    credentials: list[tuple[int, str]],
    *,
    original_name: str | None = None,
) -> CleanChatResult:
    selected_categories = normalize_clean_chat_selection(mode)
    _ensure_opentele_patched()
    output_dir.mkdir(parents=True, exist_ok=True)
    temp_dir: tempfile.TemporaryDirectory[str] | None = None
    session_files: list[Path] = []

    try:
        suffix = Path(original_name or input_path.name).suffix.lower()
        if suffix == ".zip":
            temp_dir = tempfile.TemporaryDirectory(prefix="ftgc_clnchat_zip_")
            session_files = extract_zip_sessions_safe(input_path, Path(temp_dir.name))
        elif suffix == ".session":
            if original_name:
                temp_dir = tempfile.TemporaryDirectory(prefix="ftgc_clnchat_one_")
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

            cleaned = await clean_session_chats(
                sess_file, credentials, mode=selected_categories
            )
            if cleaned:
                success_files.append(sess_file)
            else:
                failed += 1

        cleaned_count = len(success_files)
        output_path: Path | None = None
        is_zip = False

        if cleaned_count > 0:
            if cleaned_count == 1 and total == 1:
                output_path = output_dir / f"Clean_Chat_1_{uuid4().hex[:6]}.session"
                shutil.copy2(success_files[0], output_path)
            else:
                is_zip = True
                output_path = (
                    output_dir / f"Clean_Chat_{cleaned_count}_{uuid4().hex[:6]}.zip"
                )
                with zipfile.ZipFile(output_path, "w", zipfile.ZIP_DEFLATED) as archive:
                    used_names: set[str] = set()
                    for idx, sfile in enumerate(success_files, start=1):
                        arcname = sfile.name
                        if arcname in used_names:
                            arcname = f"{sfile.stem}_{idx}.session"
                        used_names.add(arcname)
                        archive.write(sfile, arcname=arcname)

        return CleanChatResult(
            total=total,
            cleaned=cleaned_count,
            failed=failed,
            output_path=output_path,
            is_zip=is_zip,
        )
    finally:
        if temp_dir is not None:
            temp_dir.cleanup()
