from __future__ import annotations

import asyncio
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

# Max concurrent join/leave operations (shared api credentials / IP ceiling).
_CHANNEL_CONCURRENCY = 8


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
            session_files = await asyncio.to_thread(
                extract_zip_sessions_safe, input_path, Path(temp_dir.name)
            )
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

        # Joining is a connect + join RPC per session. Sequential execution
        # made batches slow; a bounded semaphore (shared api credentials / IP)
        # parallelizes without flooding.
        join_semaphore = asyncio.Semaphore(min(_CHANNEL_CONCURRENCY, total or 1))

        async def join_one(index: int) -> bool:
            sess_file = session_files[index]
            if not _is_valid_sqlite_session(sess_file):
                return False
            async with join_semaphore:
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
                        from app.services.device_params import get_stable_device_params
                        device_kwargs = get_stable_device_params(sess_file)
                        client = TelegramClient(
                            stem, api_id, api_hash, receive_updates=False, **device_kwargs
                        )
                        try:
                            await client.connect()
                            if not await client.is_user_authorized():
                                # Dead auth key: unauthorized under any api_id.
                                break

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
                return joined

        join_results = await asyncio.gather(*(join_one(i) for i in range(total)))
        for index, joined in enumerate(join_results):
            if joined:
                success_files.append(session_files[index])
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
            session_files = await asyncio.to_thread(
                extract_zip_sessions_safe, input_path, Path(temp_dir.name)
            )
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

        # Leaving is a connect + leave RPC chain per session. Sequential
        # execution made batches slow; a bounded semaphore (shared api
        # credentials / IP) parallelizes without flooding. The dialog loop
        # inside a single leave_all session stays sequential (one client).
        leave_semaphore = asyncio.Semaphore(min(_CHANNEL_CONCURRENCY, total or 1))

        async def leave_one(index: int) -> bool:
            sess_file = session_files[index]
            if not _is_valid_sqlite_session(sess_file):
                return False
            async with leave_semaphore:
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
                        from app.services.device_params import get_stable_device_params
                        device_kwargs = get_stable_device_params(sess_file)
                        client = TelegramClient(
                            stem, api_id, api_hash, receive_updates=False, **device_kwargs
                        )
                        try:
                            await client.connect()
                            if not await client.is_user_authorized():
                                # Dead auth key: unauthorized under any api_id.
                                break

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
                return left

        leave_results = await asyncio.gather(*(leave_one(i) for i in range(total)))
        for index, left in enumerate(leave_results):
            if left:
                success_files.append(session_files[index])
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
