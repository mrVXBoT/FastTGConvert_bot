from __future__ import annotations

import logging
import re
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
class ChannelResult:
    total: int
    success: int
    failed: int
    output_path: Path | None = None
    is_zip: bool = False


def parse_channel_target(target: str) -> tuple[str, bool]:
    clean = target.strip()
    clean = re.sub(r"^https?://", "", clean, flags=re.IGNORECASE)
    clean = re.sub(r"^(?:t\.me/|telegram\.me/)", "", clean, flags=re.IGNORECASE)

    if clean.startswith("+"):
        return clean[1:], True
    if clean.lower().startswith("joinchat/"):
        return clean[9:], True

    clean = clean.lstrip("@")
    return clean, False


async def process_channel_join(
    input_path: Path,
    output_dir: Path,
    target: str,
    credentials: list[tuple[int, str]],
    *,
    original_name: str | None = None,
) -> ChannelResult:
    _ensure_opentele_patched()
    output_dir.mkdir(parents=True, exist_ok=True)
    temp_dir: tempfile.TemporaryDirectory[str] | None = None
    session_files: list[Path] = []

    try:
        suffix = Path(original_name or input_path.name).suffix.lower()
        if suffix == ".zip":
            temp_dir = tempfile.TemporaryDirectory(prefix="ftgc_chan_join_zip_")
            session_files = extract_zip_sessions_safe(input_path, Path(temp_dir.name))
        elif suffix == ".session":
            if original_name:
                temp_dir = tempfile.TemporaryDirectory(prefix="ftgc_chan_join_one_")
                copied = Path(temp_dir.name) / Path(original_name).name
                shutil.copy2(input_path, copied)
                session_files = [copied]
            else:
                session_files = [input_path]

        total = len(session_files)
        success_files: list[Path] = []
        failed = 0

        channel_identifier, is_private = parse_channel_target(target)

        for sess_file in session_files:
            if not _is_valid_sqlite_session(sess_file):
                failed += 1
                continue

            joined = False
            for api_id, api_hash in credentials:
                try:
                    from telethon import (  # type: ignore[import-untyped]
                        TelegramClient,
                        functions,
                    )
                except ModuleNotFoundError:
                    break

                with tempfile.TemporaryDirectory(prefix="ftgc_chan_run_") as run_tmp:
                    run_sess = Path(run_tmp) / "account.session"
                    shutil.copy2(sess_file, run_sess)
                    stem = str(run_sess.with_suffix(""))
                    client = TelegramClient(
                        stem, api_id, api_hash, receive_updates=False
                    )
                    try:
                        await client.connect()
                        if not await client.is_user_authorized():
                            continue

                        if is_private:
                            await client(
                                functions.messages.ImportChatInviteRequest(
                                    hash=channel_identifier
                                )
                            )
                        else:
                            await client(
                                functions.channels.JoinChannelRequest(
                                    channel=channel_identifier
                                )
                            )
                        joined = True
                        shutil.copy2(run_sess, sess_file)
                        break
                    except Exception as exc:  # noqa: BLE001
                        LOGGER.debug("Channel join attempt failed: %s", exc)
                    finally:
                        with suppress(Exception):
                            await client.disconnect()

            if joined:
                success_files.append(sess_file)
            else:
                failed += 1

        success_count = len(success_files)
        output_path: Path | None = None
        is_zip = False

        if success_count > 0:
            if success_count == 1 and total == 1:
                output_path = output_dir / f"Channel_Joined_1_{uuid4().hex[:6]}.session"
                shutil.copy2(success_files[0], output_path)
            else:
                is_zip = True
                output_path = (
                    output_dir / f"Channel_Joined_{success_count}_{uuid4().hex[:6]}.zip"
                )
                with zipfile.ZipFile(output_path, "w", zipfile.ZIP_DEFLATED) as archive:
                    used_names: set[str] = set()
                    for idx, sfile in enumerate(success_files, start=1):
                        arcname = sfile.name
                        if arcname in used_names:
                            arcname = f"{sfile.stem}_{idx}.session"
                        used_names.add(arcname)
                        archive.write(sfile, arcname=arcname)

        return ChannelResult(
            total=total,
            success=success_count,
            failed=failed,
            output_path=output_path,
            is_zip=is_zip,
        )
    finally:
        if temp_dir is not None:
            temp_dir.cleanup()


async def process_channel_leave(
    input_path: Path,
    output_dir: Path,
    target: str,
    credentials: list[tuple[int, str]],
    *,
    original_name: str | None = None,
) -> ChannelResult:
    _ensure_opentele_patched()
    output_dir.mkdir(parents=True, exist_ok=True)
    temp_dir: tempfile.TemporaryDirectory[str] | None = None
    session_files: list[Path] = []

    try:
        suffix = Path(original_name or input_path.name).suffix.lower()
        if suffix == ".zip":
            temp_dir = tempfile.TemporaryDirectory(prefix="ftgc_chan_leave_zip_")
            session_files = extract_zip_sessions_safe(input_path, Path(temp_dir.name))
        elif suffix == ".session":
            if original_name:
                temp_dir = tempfile.TemporaryDirectory(prefix="ftgc_chan_leave_one_")
                copied = Path(temp_dir.name) / Path(original_name).name
                shutil.copy2(input_path, copied)
                session_files = [copied]
            else:
                session_files = [input_path]

        total = len(session_files)
        success_files: list[Path] = []
        failed = 0

        leave_all = target.strip().lower() in ("all", "*", "همه")
        channel_identifier, is_private = parse_channel_target(target)

        for sess_file in session_files:
            if not _is_valid_sqlite_session(sess_file):
                failed += 1
                continue

            left = False
            for api_id, api_hash in credentials:
                try:
                    from telethon import (  # type: ignore[import-untyped]
                        TelegramClient,
                        functions,
                    )
                except ModuleNotFoundError:
                    break

                with tempfile.TemporaryDirectory(
                    prefix="ftgc_chan_leave_run_"
                ) as run_tmp:
                    run_sess = Path(run_tmp) / "account.session"
                    shutil.copy2(sess_file, run_sess)
                    stem = str(run_sess.with_suffix(""))
                    client = TelegramClient(
                        stem, api_id, api_hash, receive_updates=False
                    )
                    try:
                        await client.connect()
                        if not await client.is_user_authorized():
                            continue

                        if leave_all:
                            left_chats = 0
                            fail_chats = 0
                            total_chats = 0
                            async for dialog in client.iter_dialogs():
                                if dialog.is_channel or dialog.is_group:
                                    total_chats += 1
                                    try:
                                        if dialog.is_channel:
                                            await client(
                                                functions.channels.LeaveChannelRequest(
                                                    channel=dialog.entity
                                                )
                                            )
                                        else:
                                            await client(
                                                functions.messages.DeleteChatUserRequest(
                                                    chat_id=dialog.entity.id,
                                                    user_id="me",
                                                )
                                            )
                                        left_chats += 1
                                    except Exception:  # noqa: BLE001
                                        try:
                                            await client.delete_dialog(dialog.entity)
                                            left_chats += 1
                                        except Exception:  # noqa: BLE001
                                            fail_chats += 1

                            if total_chats == 0 or (left_chats > 0 and fail_chats == 0):
                                left = True
                            else:
                                left = False
                        else:
                            target_entity: str | object = channel_identifier
                            already_not_member = False
                            if is_private:
                                try:
                                    from telethon import (
                                        types,  # type: ignore[import-untyped]
                                    )

                                    invite_res = await client(
                                        functions.messages.CheckChatInviteRequest(
                                            hash=channel_identifier
                                        )
                                    )
                                    if isinstance(invite_res, types.ChatInvite):
                                        already_not_member = True
                                    else:
                                        target_entity = getattr(
                                            invite_res, "chat", channel_identifier
                                        )
                                except Exception:  # noqa: BLE001
                                    target_entity = channel_identifier

                            if already_not_member:
                                left = True
                            else:
                                try:
                                    await client(
                                        functions.channels.LeaveChannelRequest(
                                            channel=target_entity
                                        )
                                    )
                                    left = True
                                except Exception:  # noqa: BLE001
                                    try:
                                        await client.delete_dialog(target_entity)
                                        left = True
                                    except Exception:  # noqa: BLE001
                                        left = False

                        if left:
                            shutil.copy2(run_sess, sess_file)
                            break
                    except Exception as exc:  # noqa: BLE001
                        LOGGER.debug("Channel leave attempt failed: %s", exc)
                    finally:
                        with suppress(Exception):
                            await client.disconnect()

            if left:
                success_files.append(sess_file)
            else:
                failed += 1

        success_count = len(success_files)
        output_path: Path | None = None
        is_zip = False

        if success_count > 0:
            if success_count == 1 and total == 1:
                output_path = output_dir / f"Channel_Left_1_{uuid4().hex[:6]}.session"
                shutil.copy2(success_files[0], output_path)
            else:
                is_zip = True
                output_path = (
                    output_dir / f"Channel_Left_{success_count}_{uuid4().hex[:6]}.zip"
                )
                with zipfile.ZipFile(output_path, "w", zipfile.ZIP_DEFLATED) as archive:
                    used_names: set[str] = set()
                    for idx, sfile in enumerate(success_files, start=1):
                        arcname = sfile.name
                        if arcname in used_names:
                            arcname = f"{sfile.stem}_{idx}.session"
                        used_names.add(arcname)
                        archive.write(sfile, arcname=arcname)

        return ChannelResult(
            total=total,
            success=success_count,
            failed=failed,
            output_path=output_path,
            is_zip=is_zip,
        )
    finally:
        if temp_dir is not None:
            temp_dir.cleanup()
