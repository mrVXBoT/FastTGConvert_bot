from __future__ import annotations

import asyncio
import logging
import shutil
import tempfile
import zipfile
from collections.abc import Awaitable, Callable, Collection
from dataclasses import dataclass
from pathlib import Path
from typing import Any
from uuid import uuid4

from app.services.contacts_checker import extract_zip_sessions_safe
from app.services.file_merge import (
    _is_valid_sqlite_session,
    extract_account_identifier,
)
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
    proxy: tuple | None = None,
    flood_ceiling: int = 30,
    delete_concurrency: int = 5,
    on_progress: Callable[[int], Awaitable[None]] | None = None,
) -> bool:
    """
    Connect via Telethon and clean chats for a session account according to mode.
    Categories can contain any combination of dms, bots, groups and channels.
    The legacy string all selects every category.

    Performance: dialogs are deleted in small CONCURRENT batches (the old
    sequential per-chat loop is the reason cleaning many chats took minutes).
    The credential loop only rotates when the connection itself fails or the
    session is unauthorised — a partial deletion failure is reported honestly
    instead of re-scanning the whole account with the next credential.

    ``on_progress(done)`` is awaited after every batch with the number of
    chats deleted so far.
    """
    selected_categories = normalize_clean_chat_selection(mode)
    if not credentials or not session_file.exists():
        return False

    try:
        from telethon import TelegramClient  # type: ignore[import-untyped]
        from telethon.errors import FloodWaitError  # type: ignore[import-untyped]
    except ModuleNotFoundError:
        return False
    from contextlib import suppress

    delete_concurrency = max(delete_concurrency, 1)

    for api_id, api_hash in credentials:
        cleaned = False
        try:
            with tempfile.TemporaryDirectory(prefix="ftgc_clnchat_") as tmp_dir:
                run_sess = Path(tmp_dir) / session_file.name
                shutil.copy2(session_file, run_sess)
                stem = str(run_sess.with_suffix(""))
                from app.services.device_params import get_stable_device_params
                device_kwargs = get_stable_device_params(session_file)
                client = TelegramClient(
                    stem,
                    api_id,
                    api_hash,
                    receive_updates=False,
                    proxy=proxy,
                    flood_sleep_threshold=0,
                    **device_kwargs,
                )
                try:
                    await client.connect()
                    if not await client.is_user_authorized():  # type: ignore[attr-defined]
                        # An unauthorized session stays unauthorized under any
                        # api_id (the auth key itself is dead/banned). Rotating
                        # through every credential just multiplies a multi-
                        # second connect+probe by the number of api pairs —
                        # with 10 credentials this turned dead sessions into
                        # ~35s each and whole batches into ~30 min runs.
                        LOGGER.info(
                            "Session %s unauthorized; skipping remaining "
                            "credentials",
                            session_file.name,
                        )
                        return False

                    # ── Phase 1: scan dialogs and collect the targets ──────
                    targets: list[Any] = []
                    async for dialog in client.iter_dialogs():  # type: ignore[attr-defined]
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

                        if category in selected_categories:
                            targets.append(dialog.entity)

                    if not targets:
                        cleaned = True
                    else:
                        failed_dialogs = 0
                        deleted = 0

                        async def _delete_one(
                            entity: Any, _client: Any = client
                        ) -> None:
                            nonlocal failed_dialogs, deleted
                            try:
                                await _client.delete_dialog(entity, revoke=False)  # type: ignore[attr-defined]
                                deleted += 1
                            except FloodWaitError as exc:
                                seconds = max(
                                    0, int(getattr(exc, "seconds", 0) or 0)
                                )
                                if seconds <= flood_ceiling:
                                    LOGGER.info(
                                        "Clean chat flood-waiting %ds", seconds
                                    )
                                    await asyncio.sleep(seconds)
                                    try:
                                        await _client.delete_dialog(  # type: ignore[attr-defined]
                                            entity, revoke=False
                                        )
                                        deleted += 1
                                    except Exception as exc2:  # noqa: BLE001
                                        failed_dialogs += 1
                                        LOGGER.warning(
                                            "Failed cleaning dialog %s after "
                                            "flood wait: %s",
                                            getattr(entity, "id", entity),
                                            exc2,
                                        )
                                else:
                                    failed_dialogs += 1
                                    LOGGER.warning(
                                        "Skipped dialog %s: flood wait %ds "
                                        "exceeds ceiling %ds",
                                        getattr(entity, "id", entity),
                                        seconds,
                                        flood_ceiling,
                                    )
                            except Exception as exc:  # noqa: BLE001
                                failed_dialogs += 1
                                LOGGER.warning(
                                    "Failed cleaning dialog %s: %s",
                                    getattr(entity, "id", entity),
                                    exc,
                                )

                        # ── Phase 2: delete concurrently, batch by batch ───
                        for start in range(0, len(targets), delete_concurrency):
                            chunk = targets[start : start + delete_concurrency]
                            await asyncio.gather(*(_delete_one(entity) for entity in chunk))
                            if on_progress is not None:
                                await on_progress(deleted)

                        cleaned = failed_dialogs == 0
                finally:
                    with suppress(Exception):
                        await client.disconnect()
                if cleaned:
                    shutil.copy2(run_sess, session_file)
                    return True
        except Exception as exc:  # noqa: BLE001
            # Some failures mean the SESSION itself is dead, not the
            # credential: the auth key was revoked or the account was
            # deactivated/banned. Retrying those with another api_id is pure
            # waste — each attempt costs a fresh connect handshake. Only
            # transient failures (connect errors, timeouts, other RPC errors)
            # deserve the next credential pair.
            from telethon.errors import (  # type: ignore[import-untyped]
                AuthKeyUnregisteredError,
                UserDeactivatedBanError,
                UserDeactivatedError,
            )

            if isinstance(exc, (AuthKeyUnregisteredError, UserDeactivatedError, UserDeactivatedBanError)):
                LOGGER.info(
                    "Session %s is deactivated/banned (%s); skipping remaining "
                    "credentials",
                    session_file.name,
                    type(exc).__name__,
                )
                return False
            LOGGER.warning(
                "Clean chat attempt failed with api_id=%d: %s", api_id, exc
            )

    return False


class _ProgressAggregator:
    """Sums per-session deletion progress into one shared counter and reports
    both deletions and completed sessions so long dead-session phases keep
    the user-facing status message moving."""

    def __init__(
        self,
        on_progress: Callable[[int, int], Awaitable[None]],
        lock: asyncio.Lock,
    ) -> None:
        self._on_progress = on_progress
        self._lock = lock
        self.done = 0
        self.sessions_done = 0

    async def add_deletions(self, count: int) -> None:
        async with self._lock:
            self.done += count
        await self._emit()

    async def add_session(self) -> None:
        async with self._lock:
            self.sessions_done += 1
        await self._emit()

    async def _emit(self) -> None:
        await self._on_progress(self.done, self.sessions_done)

    async def __call__(self, count: int) -> None:
        await self.add_deletions(count)


async def process_clean_chat(
    input_path: Path,
    output_dir: Path,
    mode: str | Collection[str],
    credentials: list[tuple[int, str]],
    *,
    original_name: str | None = None,
    proxy: tuple | None = None,
    concurrency: int = 5,
    flood_ceiling: int = 30,
    delete_concurrency: int = 5,
    on_progress: Callable[[int, int], Awaitable[None]] | None = None,
) -> CleanChatResult:
    """Clean chats in all uploaded sessions, returning a result summary.

    ``on_progress(deleted, sessions_done)`` is awaited after every deletion
    batch and after every finished session (deleted chats so far, sessions
    completed so far).
    """
    selected_categories = normalize_clean_chat_selection(mode)
    if concurrency < 1:
        raise ValueError("invalid_concurrency")
    _ensure_opentele_patched()
    output_dir.mkdir(parents=True, exist_ok=True)
    temp_dir: tempfile.TemporaryDirectory[str] | None = None
    session_files: list[Path] = []

    try:
        suffix = Path(original_name or input_path.name).suffix.lower()
        if suffix == ".zip":
            temp_dir = tempfile.TemporaryDirectory(prefix="ftgc_clnchat_zip_")
            session_files = await asyncio.to_thread(
                extract_zip_sessions_safe, input_path, Path(temp_dir.name)
            )
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

        LOGGER.info(
            "Starting Clean Chat (Mode: %s) for %d session(s)...",
            sorted(selected_categories),
            total,
        )

        semaphore = asyncio.Semaphore(concurrency)
        progress_agg = (
            _ProgressAggregator(on_progress, asyncio.Lock()) if on_progress else None
        )

        async def work(sess_file: Path) -> bool:
            async with semaphore:
                if not _is_valid_sqlite_session(sess_file):
                    if progress_agg is not None:
                        await progress_agg.add_session()
                    return False
                try:
                    return await clean_session_chats(
                        sess_file,
                        credentials,
                        mode=selected_categories,
                        proxy=proxy,
                        flood_ceiling=flood_ceiling,
                        delete_concurrency=delete_concurrency,
                        on_progress=progress_agg,
                    )
                finally:
                    if progress_agg is not None:
                        await progress_agg.add_session()

        results = await asyncio.gather(*(work(sess) for sess in session_files))
        for sess_file, cleaned in zip(session_files, results):
            identifier, uid, phone = extract_account_identifier(sess_file)
            if cleaned:
                success_files.append(sess_file)
                LOGGER.info(
                    "Clean Chat: Account=%s | Phone=%s | UserID=%s → SUCCESS",
                    identifier,
                    f"+{phone}" if phone else "N/A",
                    uid or "N/A",
                )
            else:
                failed += 1
                LOGGER.warning(
                    "Clean Chat: Account=%s | Phone=%s | UserID=%s → FAILED",
                    identifier,
                    f"+{phone}" if phone else "N/A",
                    uid or "N/A",
                )

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

        LOGGER.info(
            "Clean Chat Summary: Total=%d | Cleaned=%d | Failed=%d | Output=%s",
            total,
            cleaned_count,
            failed,
            output_path.name if output_path else "None",
        )

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
