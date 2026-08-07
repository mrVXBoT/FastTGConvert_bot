import asyncio
import contextlib
import json
import logging
import random
import shutil
import tempfile
import time
from collections.abc import Mapping
from contextlib import suppress
from pathlib import Path
from typing import Any, Literal
from uuid import uuid4

from aiogram import Bot, F, Router, html
from aiogram.filters import StateFilter
from aiogram.fsm.context import FSMContext
from aiogram.types import (
    BufferedInputFile,
    CallbackQuery,
    FSInputFile,
    InlineKeyboardButton,
    InlineKeyboardMarkup,
    Message,
)
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session, sessionmaker

from app.config import Settings
from app.contacts_results import (
    contacts_report_caption,
    contacts_result_menu,
    contacts_status_zip_caption,
    render_contacts_result,
)
from app.db.models import Job, User, utcnow
from app.db.repositories import (
    generate_unique_display_id,
    get_user_language,
    upsert_user,
)
from app.keyboards import (
    account_age_result_menu,
    account_txt_result_menu,
    cancel_menu,
    channel_result_menu,
    clean_chat_choice_menu,
    clean_chat_result_menu,
    clear_contacts_result_menu,
    delete_contact_result_menu,
    delete_contact_selection_menu,
    file_merge_choice_menu,
    file_merge_result_menu,
    file_split_choice_menu,
    file_split_result_menu,
    fresh_session_2fa_menu,
    fresh_session_confirm_menu,
    fresh_session_result_menu,
    kill_sessions_confirm_menu,
    kill_sessions_result_menu,
    list_checker_cancel_menu,
    list_checker_result_menu,
    main_menu,
    mass_message_confirm_menu,
    mass_message_delay_menu,
    mass_message_live_menu,
    mass_message_recipients_menu,
    otp_initial_menu,
    privacy_custom_menu,
    privacy_mode_menu,
    privacy_presets_menu,
    privacy_result_menu,
    privacy_value_menu,
    profile_setup_account_menu,
    profile_setup_result_menu,
    quick_action_menu,
    session_json_result_menu,
    session_to_tdata_result_menu,
    tdata_to_session_result_menu,
    two_factor_cancel_menu,
    two_factor_result_menu,
)
from app.locales import (
    ACCOUNT_AGE_MESSAGES,
    ACCOUNT_TO_TXT_MESSAGES,
    ACCOUNT_TO_TXT_PROMPTS,
    ANALYSIS_MESSAGES,
    ANALYZE_PROMPTS,
    ARCHIVE_ERRORS,
    CANCEL_LABELS,
    CHANGE_2FA_PROMPTS,
    CHANNEL_JOIN_PROMPTS,
    CHANNEL_LEAVE_PROMPTS,
    CHANNEL_MESSAGES,
    CHECK_CONTACTS_MESSAGES,
    CHECK_CONTACTS_PROMPTS,
    CLEAN_CHAT_MESSAGES,
    CLEAN_CHAT_MODE_PROMPT,
    CLEAN_CHAT_SELECTION_ACTIONS,
    CLEAR_CONTACTS_MESSAGES,
    DELETE_CONTACT_MESSAGES,
    DELETE_CONTACT_SELECT_PROMPT,
    DIRECT_FILE_MESSAGES,
    DIRECT_FILE_PROMPTS,
    DISABLE_2FA_PROMPTS,
    DOWNLOAD_ERRORS,
    ENTER_ACCOUNT_AGE_PROMPT,
    ENTER_CHANNEL_JOIN_TARGET_PROMPT,
    ENTER_CHANNEL_LEAVE_TARGET_PROMPT,
    ENTER_CLEAN_CHAT_PROMPT,
    ENTER_CLEAR_CONTACTS_PROMPT,
    ENTER_CURRENT_2FA_PROMPT,
    ENTER_DELETE_CONTACT_PROMPT,
    ENTER_FRESH_SESSION_PROMPT,
    ENTER_KILL_SESSIONS_PROMPT,
    ENTER_NEW_2FA_PROMPT,
    ENTER_PROFILE_SETUP_PROMPT,
    FILE_MERGE_MESSAGES,
    FILE_MERGE_PROMPTS,
    FRESH_SESSION_2FA_PROMPT,
    FRESH_SESSION_CONFIRM_PROMPT,
    FRESH_SESSION_MESSAGES,
    KILL_SESSIONS_CONFIRM_PROMPT,
    KILL_SESSIONS_MESSAGES,
    LIST_CHECKER_MESSAGES,
    MASS_MESSAGE_MESSAGES,
    MASS_MESSAGE_PROMPTS,
    PRIVACY_SETTINGS_MESSAGES,
    PROFILE_SETUP_ABOUT_PROMPT,
    PROFILE_SETUP_ACCOUNT_PROMPT,
    PROFILE_SETUP_MESSAGES,
    PROFILE_SETUP_NAME_PROMPT,
    PROFILE_SETUP_PHOTO_PROMPT,
    PROFILE_SETUP_USERNAME_PROMPT,
    READ_OTP_MESSAGES,
    RESET_2FA_PROMPTS,
    SESSION_CHECK_PROMPTS,
    SESSION_TO_JSON_MESSAGES,
    SESSION_TO_JSON_PROMPTS,
    SESSION_TO_TDATA_MESSAGES,
    SESSION_TO_TDATA_PROMPTS,
    SPAM_CHECK_PROMPTS,
    SPLIT_MESSAGES,
    SPLIT_PROMPTS,
    TDATA_TO_SESSION_MESSAGES,
    TDATA_TO_SESSION_PROMPTS,
    TWO_FACTOR_ACCOUNT_CURRENT_PROMPT,
    TWO_FACTOR_ACCOUNT_NEW_PROMPT,
    TWO_FACTOR_ERRORS,
    TWO_FACTOR_MESSAGES,
    action_message,
)
from app.services.account_age import (
    AccountAgeInfo,
    AccountAgeResult,
    format_account_age_report,
    process_account_age_check,
)
from app.services.account_to_txt import process_account_to_txt
from app.services.channel import (
    process_channel_join,
    process_channel_leave,
)
from app.services.clean_chat import CLEAN_CHAT_CATEGORIES, process_clean_chat
from app.services.clear_contacts import process_clear_contacts
from app.services.contacts_checker import (
    ContactsCheckCancelled,
    ContactsProgress,
    extract_zip_sessions_safe,
    process_contacts_check,
)
from app.services.delete_contact import (
    fetch_input_contacts,
    process_delete_contacts,
)
from app.services.file_merge import (
    _is_valid_sqlite_session,
    inspect_mergeable_sessions,
    process_file_merge,
)
from app.services.files import (
    UnsafeArchiveError,
    allocate_path,
    analyze_file,
    safe_filename,
)
from app.services.fresh_session import process_fresh_sessions
from app.services.jobs import JobCancelled, JobProgress
from app.services.kill_sessions import process_kill_sessions
from app.services.list_checker import compare_archive_files
from app.services.mass_message import (
    GlobalRateLimiter,
    Recipient,
    create_telethon_client_for_session,
    extract_contacts_from_sessions,
    format_mass_message_summary,
    generate_mass_message_report,
    parse_recipients_from_file,
    send_mass_message_to_recipient,
)
from app.services.privacy_settings import process_privacy_settings
from app.services.profile_setup import (
    fetch_account_profile,
    package_profile_setup_results,
    update_account_profile,
)
from app.services.proxy import resolve_user_proxy
from app.services.records import create_file_and_job, finish_job
from app.services.session_split import (
    SessionSplitResult,
    inspect_session_split,
    process_session_split,
)
from app.services.session_to_json import process_session_to_json
from app.services.session_to_tdata import (
    live_failure_label,
    process_session_to_tdata_conversion,
)
from app.services.tdata_to_session import process_tdata_to_session_conversion
from app.services.two_factor import (
    TwoFactorResult,
    edit_two_factor_session,
    package_two_factor_batch,
    process_reset_2fa,
    stage_two_factor_sessions,
)
from app.session_checker import (
    SessionCheckEntry,
    SessionProgress,
    build_status_zips,
    check_sessions_detailed,
)
from app.session_results import (
    render_session_result,
    render_spam_result,
    session_result_menu,
    status_zip_caption,
)
from app.states import (
    AccountAge,
    AccountToTxt,
    AnalyzeFile,
    Change2FA,
    ChannelJoin,
    ChannelLeave,
    CleanChat,
    ClearContacts,
    ConvertSessionToJson,
    ConvertSessionToTdata,
    ConvertTdataToSession,
    DeleteContact,
    DirectFile,
    Disable2FA,
    FileMerge,
    FreshSession,
    KillSessions,
    ListChecker,
    MassMessage,
    PrivacySettings,
    ProfileSetup,
    ReadOTP,
    Reset2FA,
    SplitFile,
)
from app.ui import EmojiRegistry
from app.ui.styles import ButtonStyle

router = Router(name="files")
LOGGER = logging.getLogger(__name__)
_DIRECT_FILE_TIMEOUT_SECONDS = 15
ACTIVE_MASS_MESSAGE_JOBS: dict[int, dict[str, Any]] = {}

# Global cap on how many mass-message jobs may run at once. Prevents a flood
# of concurrent mass campaigns saturating the Telegram API credentials pool.
MASS_MESSAGE_MAX_CONCURRENT_JOBS = 3
MASS_MESSAGE_SEMAPHORE = asyncio.Semaphore(MASS_MESSAGE_MAX_CONCURRENT_JOBS)

# Cancel events for running contacts checks, keyed by user id.
ACTIVE_CONTACTS_JOBS: dict[int, asyncio.Event] = {}

# Cancel events + progress for running conversions, keyed by (user_id, tool).
ACTIVE_CONVERSION_JOBS: dict[tuple[int, str], tuple[asyncio.Event, JobProgress]] = {}
ACTIVE_2FA_JOBS: dict[tuple[int, str], asyncio.Event] = {}


def user_language(session_factory: sessionmaker[Session], user_id: int) -> str:
    with session_factory() as session:
        return get_user_language(session, user_id)


def human_size(size: int) -> str:
    value = float(size)
    for unit in ("B", "KB", "MB", "GB"):
        if value < 1024 or unit == "GB":
            return f"{value:.2f} {unit}"
        value /= 1024
    return f"{value:.2f} GB"


async def update_progress_bar(message: Message, base_text: str) -> None:
    # Indeterminate spinner: this operation has no real progress to report,
    # so show an honest "working" animation instead of a fake percentage bar.
    frames = ["⠋", "⠙", "⠹", "⠸", "⠼", "⠴", "⠦", "⠧", "⠇", "⠏"]
    divider = EmojiRegistry.divider_line()
    try:
        i = 0
        while True:
            frame = frames[i % len(frames)]
            try:
                await message.edit_text(f"{base_text}\n{divider}\n<code>{frame}</code>")
            except Exception as exc:  # noqa: BLE001
                LOGGER.debug("Progress message update skipped: %s", exc)
            i += 1
            await asyncio.sleep(0.4)
    except asyncio.CancelledError:
        pass


async def _stop_progress(task: asyncio.Task[None]) -> None:
    """Cancel *task* and wait for it to finish before returning."""
    task.cancel()
    try:
        await task
    except asyncio.CancelledError:
        pass


async def update_contacts_progress(
    message: Message,
    progress: ContactsProgress,
    base_text: str,
    language: str = "en",
) -> None:
    """Live progress loop for contacts checks: ``✅ done / total`` + cancel."""
    cancel_label = CANCEL_LABELS.get(language, CANCEL_LABELS["en"])
    cancel_markup = InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(
                    text=f"❌ {cancel_label}",
                    callback_data="contacts_stat:cancel",
                    style=ButtonStyle.DANGER.value,
                )
            ]
        ]
    )
    divider = EmojiRegistry.divider_line()
    try:
        while True:
            total = progress.total
            done = progress.done
            if total:
                pct = round(done * 100 / total)
                width = 12
                filled = round(width * pct / 100)
                bar = "▓" * filled + "░" * (width - filled)
                body = (
                    f"{base_text}\n{divider}\n"
                    f"✅ {done} / {total}\n<code>{bar}</code>  {pct:3d}%"
                )
            else:
                body = f"{base_text}\n{divider}\n⏳"
            try:
                await message.edit_text(body, reply_markup=cancel_markup)
            except Exception as exc:  # noqa: BLE001
                LOGGER.debug("Contacts progress update skipped: %s", exc)
            if total and done >= total:
                break
            await asyncio.sleep(1.2)
    except asyncio.CancelledError:
        pass


async def update_session_progress(
    message: Message,
    progress: SessionProgress,
    base_text: str,
) -> None:
    """Live progress loop for session checks: ``✅ done / total`` + progress bar."""
    divider = EmojiRegistry.divider_line()
    try:
        while True:
            total = progress.total
            done = progress.done
            if total:
                pct = round(done * 100 / total)
                width = 12
                filled = round(width * pct / 100)
                bar = "▓" * filled + "░" * (width - filled)
                body = (
                    f"{base_text}\n{divider}\n"
                    f"✅ {done} / {total}\n<code>{bar}</code>  {pct:3d}%"
                )
            else:
                body = f"{base_text}\n{divider}\n⏳"
            try:
                await message.edit_text(body)
            except Exception as exc:  # noqa: BLE001
                LOGGER.debug("Session progress update skipped: %s", exc)
            if total and done >= total:
                break
            await asyncio.sleep(1.2)
    except asyncio.CancelledError:
        pass


async def update_conversion_progress(
    message: Message,
    progress: JobProgress,
    base_text: str,
    tool: str,
    language: str = "en",
) -> None:
    """Live progress loop for conversion jobs: ``✅ done / total`` + cancel."""
    cancel_label = CANCEL_LABELS.get(language, CANCEL_LABELS["en"])
    cancel_markup = InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(
                    text=f"❌ {cancel_label}",
                    callback_data=f"conv:cancel:{tool}",
                    style=ButtonStyle.DANGER.value,
                )
            ]
        ]
    )
    divider = EmojiRegistry.divider_line()
    try:
        while True:
            total = progress.total
            done = progress.done
            if total:
                pct = round(done * 100 / total)
                width = 12
                filled = round(width * pct / 100)
                bar = "▓" * filled + "░" * (width - filled)
                body = (
                    f"{base_text}\n{divider}\n"
                    f"✅ {done} / {total}\n<code>{bar}</code>  {pct:3d}%"
                )
            else:
                body = f"{base_text}\n{divider}\n⏳"
            try:
                await message.edit_text(body, reply_markup=cancel_markup)
            except Exception as exc:  # noqa: BLE001
                LOGGER.debug("Conversion progress update skipped: %s", exc)
            if total and done >= total:
                break
            await asyncio.sleep(1.2)
    except asyncio.CancelledError:
        pass


def _truncate_detail_lines(lines: list[str], budget: int = 3800) -> tuple[str, int]:
    """Join *lines* into a string staying under *budget* chars; return (text, skipped)."""
    skipped = 0
    kept: list[str] = []
    total_len = 0
    for line in lines:
        if total_len + len(line) + 1 > budget:
            skipped += 1
            continue
        kept.append(line)
        total_len += len(line) + 1
    return "\n".join(kept), skipped


def _format_duration(seconds: float) -> str:
    """Format an elapsed duration like the reference bot: ``37s (0.6min)``."""
    if seconds < 0:
        seconds = 0.0
    return f"{seconds:.0f}s ({seconds / 60:.1f}min)"


def _conversion_stats_report(
    lang_msgs: Mapping[str, str],
    total: int,
    converted: int,
    failed: int,
    elapsed: float,
    *,
    live_verified: bool = True,
) -> str:
    """Render the ``🎊 Conversion complete`` stats card with duration & speed.

    When *live_verified* is False (no API credentials configured) an explicit
    warning is appended so offline-only results are never mistaken for live.
    """
    rate = total / elapsed if elapsed > 0 else 0.0
    pct_ok = converted * 100 / total if total else 0.0
    pct_failed = failed * 100 / total if total else 0.0
    text = lang_msgs["stats"].format(
        total=total,
        converted=converted,
        failed=failed,
        duration=_format_duration(elapsed),
        speed=f"{rate:.1f}",
        pct_converted=f"{pct_ok:.1f}",
        pct_failed=f"{pct_failed:.1f}",
    )
    if not live_verified:
        text += lang_msgs.get("stats_unverified", "")
    return text


async def _send_status_zips(
    message: Message,
    path: Path,
    entries: list[SessionCheckEntry],
    language: str = "en",
) -> None:
    """
    Regroup the checked sessions into per-status ZIP files and send them as
    documents, like the reference bot ("📦 No Restriction - 9 accounts").
    """
    try:
        import tempfile

        with tempfile.TemporaryDirectory(prefix="ftgc_status_zips_") as tmp:
            archives = await asyncio.to_thread(
                build_status_zips, path, entries, Path(tmp)
            )
            for zip_path, status, count in archives:
                caption = status_zip_caption(status, count, language)
                await message.answer_document(
                    FSInputFile(zip_path, filename=zip_path.name),
                    caption=caption,
                )
    except Exception:
        LOGGER.exception(
            "Failed to send status ZIPs for user %s",
            message.from_user.id if message.from_user else "?",
        )


async def download_document(
    message: Message, bot: Bot, settings: Settings, language: str = "en"
) -> tuple[Path, str]:
    errs = DOWNLOAD_ERRORS.get(language, DOWNLOAD_ERRORS["en"])
    document = message.document
    if document is None:
        raise ValueError(errs["document_required"])
    if document.file_size and document.file_size > settings.max_upload_bytes:
        raise ValueError(errs["file_too_large"].format(max_mb=settings.max_upload_mb))

    name = safe_filename(document.file_name)
    suffix = Path(name).suffix[:16]
    destination = allocate_path(settings.storage_dir / "inbox", suffix)
    try:
        await bot.download(document, destination=destination)
        if destination.stat().st_size > settings.max_upload_bytes:
            raise ValueError(
                errs["file_too_large"].format(max_mb=settings.max_upload_mb)
            )
    except Exception:
        LOGGER.exception("Document download failed")
        destination.unlink(missing_ok=True)
        raise
    return destination, name


@router.callback_query(F.data == "tool:session_check")
async def request_session_check(
    callback: CallbackQuery,
    state: FSMContext,
    session_factory: sessionmaker[Session],
) -> None:
    language = user_language(session_factory, callback.from_user.id)
    await state.set_state(AnalyzeFile.waiting_for_file)
    await state.update_data(session_check=True, live_spam_check=False)
    await callback.answer()
    if isinstance(callback.message, Message):
        await callback.message.edit_text(
            SESSION_CHECK_PROMPTS.get(language, SESSION_CHECK_PROMPTS["en"]),
            reply_markup=cancel_menu(language),
        )


@router.callback_query(F.data == "tool:spam_check")
async def request_spam_check(
    callback: CallbackQuery,
    state: FSMContext,
    session_factory: sessionmaker[Session],
) -> None:
    language = user_language(session_factory, callback.from_user.id)
    await state.set_state(AnalyzeFile.waiting_for_file)
    await state.update_data(session_check=True, live_spam_check=True)
    await callback.answer()
    if isinstance(callback.message, Message):
        await callback.message.edit_text(
            SPAM_CHECK_PROMPTS.get(language, SPAM_CHECK_PROMPTS["en"]),
            reply_markup=cancel_menu(language),
        )


@router.callback_query(F.data == "tool:check_contacts")
async def request_check_contacts(
    callback: CallbackQuery,
    state: FSMContext,
    session_factory: sessionmaker[Session],
) -> None:
    language = user_language(session_factory, callback.from_user.id)
    await state.set_state(AnalyzeFile.waiting_for_file)
    await state.update_data(
        session_check=False, live_spam_check=False, check_contacts=True
    )
    await callback.answer()
    if isinstance(callback.message, Message):
        await callback.message.edit_text(
            CHECK_CONTACTS_PROMPTS.get(language, CHECK_CONTACTS_PROMPTS["en"]),
            reply_markup=cancel_menu(language),
        )


@router.callback_query(F.data == "tool:session_to_tdata")
async def request_session_to_tdata(
    callback: CallbackQuery,
    state: FSMContext,
    session_factory: sessionmaker[Session],
) -> None:
    language = user_language(session_factory, callback.from_user.id)
    await state.set_state(ConvertSessionToTdata.waiting_for_file)
    await callback.answer()
    if isinstance(callback.message, Message):
        await callback.message.edit_text(
            SESSION_TO_TDATA_PROMPTS.get(language, SESSION_TO_TDATA_PROMPTS["en"]),
            reply_markup=cancel_menu(language),
        )


@router.callback_query(F.data == "tool:tdata_to_session")
async def request_tdata_to_session(
    callback: CallbackQuery,
    state: FSMContext,
    session_factory: sessionmaker[Session],
) -> None:
    language = user_language(session_factory, callback.from_user.id)
    await state.set_state(ConvertTdataToSession.waiting_for_file)
    await callback.answer()
    if isinstance(callback.message, Message):
        await callback.message.edit_text(
            TDATA_TO_SESSION_PROMPTS.get(language, TDATA_TO_SESSION_PROMPTS["en"]),
            reply_markup=cancel_menu(language),
        )


@router.callback_query(F.data == "tool:account_to_txt")
async def request_account_to_txt(
    callback: CallbackQuery,
    state: FSMContext,
    session_factory: sessionmaker[Session],
) -> None:
    language = user_language(session_factory, callback.from_user.id)
    await state.set_state(AccountToTxt.waiting_for_file)
    await callback.answer()
    if isinstance(callback.message, Message):
        await callback.message.edit_text(
            ACCOUNT_TO_TXT_PROMPTS.get(language, ACCOUNT_TO_TXT_PROMPTS["en"]),
            reply_markup=cancel_menu(language),
        )


@router.callback_query(F.data == "tool:session_to_json")
async def request_session_to_json(
    callback: CallbackQuery,
    state: FSMContext,
    session_factory: sessionmaker[Session],
) -> None:
    language = user_language(session_factory, callback.from_user.id)
    await state.set_state(ConvertSessionToJson.waiting_for_file)
    await callback.answer()
    if isinstance(callback.message, Message):
        await callback.message.edit_text(
            SESSION_TO_JSON_PROMPTS.get(language, SESSION_TO_JSON_PROMPTS["en"]),
            reply_markup=cancel_menu(language),
        )


@router.callback_query(F.data == "tool:analyze")
async def request_analysis(
    callback: CallbackQuery,
    state: FSMContext,
    session_factory: sessionmaker[Session],
) -> None:
    language = user_language(session_factory, callback.from_user.id)
    await state.set_state(AnalyzeFile.waiting_for_file)
    await state.update_data(
        session_check=False, live_spam_check=False, check_contacts=False
    )
    await callback.answer()
    if isinstance(callback.message, Message):
        await callback.message.edit_text(
            ANALYZE_PROMPTS.get(language, ANALYZE_PROMPTS["en"]),
            reply_markup=cancel_menu(language),
        )


@router.message(AnalyzeFile.waiting_for_file, F.document)
async def analyze_document(
    message: Message,
    bot: Bot,
    state: FSMContext,
    settings: Settings,
    session_factory: sessionmaker[Session],
) -> None:
    if message.from_user is None or message.document is None:
        return
    language = user_language(session_factory, message.from_user.id)
    msgs = ANALYSIS_MESSAGES.get(language, ANALYSIS_MESSAGES["en"])

    status = await message.answer(msgs["analyzing"])
    progress_task = asyncio.create_task(update_progress_bar(status, msgs["analyzing"]))

    path: Path | None = None
    try:
        try:
            path, name = await download_document(message, bot, settings, language)
            state_data = await state.get_data()
            user_proxy = resolve_user_proxy(session_factory, message.from_user.id)
            if state_data.get("check_contacts"):
                cnt_msgs = CHECK_CONTACTS_MESSAGES.get(
                    language, CHECK_CONTACTS_MESSAGES["en"]
                )
                user_id = message.from_user.id
                cancel_event = asyncio.Event()
                ACTIVE_CONTACTS_JOBS[user_id] = cancel_event
                progress = ContactsProgress()
                progress_task = asyncio.create_task(
                    update_contacts_progress(
                        status, progress, cnt_msgs["checking"], language
                    )
                )
                try:
                    contacts_res = await process_contacts_check(
                        path,
                        output_dir=settings.storage_dir / "outbox",
                        credentials=settings.api_credential_list,
                        proxy=user_proxy,
                        concurrency=settings.contacts_check_concurrency,
                        per_session_timeout=settings.contacts_check_timeout,
                        flood_wait_ceiling=settings.contacts_flood_ceiling,
                        progress=progress,
                        cancel_event=cancel_event,
                    )
                except ContactsCheckCancelled:
                    await _stop_progress(progress_task)
                    await status.edit_text(
                        EmojiRegistry.enrich_text(
                            f"❌ {html.quote(cnt_msgs['cancelled'])}"
                        ),
                        reply_markup=main_menu(language),
                    )
                    await state.clear()
                    return
                finally:
                    ACTIVE_CONTACTS_JOBS.pop(user_id, None)
                await _stop_progress(progress_task)
                try:
                    await status.edit_text(
                        render_contacts_result(contacts_res, language),
                        reply_markup=contacts_result_menu(contacts_res, language),
                    )
                    for zip_path, status_label, count in contacts_res.zip_paths:
                        await message.answer_document(
                            FSInputFile(zip_path, filename=zip_path.name),
                            caption=contacts_status_zip_caption(
                                status_label, count, language
                            ),
                        )
                    if contacts_res.report_path is not None:
                        await message.answer_document(
                            FSInputFile(
                                contacts_res.report_path,
                                filename=contacts_res.report_path.name,
                            ),
                            caption=contacts_report_caption(language),
                        )
                finally:
                    for zip_path, _label, _count in contacts_res.zip_paths:
                        zip_path.unlink(missing_ok=True)
                    if contacts_res.report_path is not None:
                        contacts_res.report_path.unlink(missing_ok=True)
                await state.clear()
                return
            if state_data.get("session_check"):
                live_check = state_data.get("live_spam_check", False)
                sess_progress = SessionProgress()
                await _stop_progress(progress_task)
                progress_task = asyncio.create_task(
                    update_session_progress(status, sess_progress, msgs["analyzing"])
                )
                try:
                    result, entries = await check_sessions_detailed(
                        path,
                        credentials=settings.api_credential_list,
                        timeout=settings.spambot_timeout,
                        proxy=user_proxy,
                        progress=sess_progress,
                    )
                finally:
                    await _stop_progress(progress_task)
                render_func = (
                    render_spam_result if live_check else render_session_result
                )
                await status.edit_text(
                    render_func(result, language),
                    reply_markup=session_result_menu(
                        result, language, spam_mode=live_check
                    ),
                )
                await _send_status_zips(message, path, entries, language)
                await state.clear()
                return
            analysis = await asyncio.to_thread(analyze_file, path, name)
            with session_factory() as session:
                user = upsert_user(
                    session, message.from_user.id, message.from_user.username
                )
                _, job = create_file_and_job(
                    session,
                    user_id=user.id,
                    telegram_file_id=message.document.file_id,
                    original_name=name,
                    storage_path=path,
                    analysis=analysis,
                    operation="analyze",
                    retention_minutes=settings.retention_minutes,
                )
                finish_job(session, job)

            archive_text = ""
            if analysis.archive_members is not None:
                archive_text = (
                    f"\n{msgs['zip_members']}: <b>{analysis.archive_members}</b>"
                    f"\n{msgs['uncompressed_size']}: <b>{human_size(analysis.archive_uncompressed_bytes or 0)}</b>"
                )
            await _stop_progress(progress_task)
            await status.edit_text(
                f"{msgs['completed']}\n{EmojiRegistry.divider_line()}\n"
                f"{msgs['name']}: <code>{html.quote(name)}</code>\n"
                f"{msgs['type']}: <code>{html.quote(analysis.media_type)}</code>\n"
                f"{msgs['size']}: <b>{human_size(analysis.size_bytes)}</b>\n"
                f"SHA-256:\n<code>{analysis.sha256}</code>{archive_text}",
                reply_markup=main_menu(language),
            )
            await state.clear()
        finally:
            if path is not None:
                path.unlink(missing_ok=True)
    except (ValueError, UnsafeArchiveError) as exc:
        await _stop_progress(progress_task)
        err_code = str(exc)
        archive_errs = ARCHIVE_ERRORS.get(language, ARCHIVE_ERRORS["en"])
        err_msg = archive_errs.get(err_code, str(exc))
        state_data = await state.get_data()
        if state_data.get("check_contacts"):
            prompt = CHECK_CONTACTS_PROMPTS.get(language, CHECK_CONTACTS_PROMPTS["en"])
        elif state_data.get("session_check"):
            if state_data.get("live_spam_check"):
                prompt = SPAM_CHECK_PROMPTS.get(language, SPAM_CHECK_PROMPTS["en"])
            else:
                prompt = SESSION_CHECK_PROMPTS.get(
                    language, SESSION_CHECK_PROMPTS["en"]
                )
        else:
            prompt = ANALYZE_PROMPTS.get(language, ANALYZE_PROMPTS["en"])

        await status.edit_text(
            f"❌ {html.quote(err_msg)}\n\n{prompt}",
            reply_markup=cancel_menu(language),
        )
    except Exception:
        LOGGER.exception("File analysis failed for user %s", message.from_user.id)
        if path is not None:
            path.unlink(missing_ok=True)
        await _stop_progress(progress_task)
        await status.edit_text(
            msgs["internal_error"],
            reply_markup=main_menu(language),
        )
        await state.clear()


@router.callback_query(F.data == "contacts_stat:noop")
async def handle_contacts_stat_noop(callback: CallbackQuery) -> None:
    await callback.answer()


@router.callback_query(F.data == "contacts_stat:cancel")
async def contacts_stat_cancel(callback: CallbackQuery) -> None:
    if callback.from_user is not None:
        event = ACTIVE_CONTACTS_JOBS.pop(callback.from_user.id, None)
        if event is not None:
            event.set()
    await callback.answer()


@router.callback_query(F.data == "contacts_stat:retry")
async def contacts_stat_retry(
    callback: CallbackQuery,
    state: FSMContext,
    session_factory: sessionmaker[Session],
) -> None:
    if callback.from_user is None:
        return
    language = user_language(session_factory, callback.from_user.id)
    await state.set_state(AnalyzeFile.waiting_for_file)
    await state.update_data(
        session_check=False, live_spam_check=False, check_contacts=True
    )
    await callback.answer()
    if isinstance(callback.message, Message):
        await callback.message.edit_text(
            CHECK_CONTACTS_PROMPTS.get(language, CHECK_CONTACTS_PROMPTS["en"]),
            reply_markup=cancel_menu(language),
        )


@router.callback_query(F.data == "contacts_stat:home")
async def contacts_stat_home(
    callback: CallbackQuery,
    state: FSMContext,
    session_factory: sessionmaker[Session],
) -> None:
    if callback.from_user is None:
        return
    from app.handlers.start import clear_state_and_file

    await clear_state_and_file(state)
    language = user_language(session_factory, callback.from_user.id)
    await callback.answer()
    if isinstance(callback.message, Message):
        await callback.message.edit_text(
            action_message(language, 3), reply_markup=main_menu(language)
        )


@router.callback_query(F.data.startswith("conv:cancel:"))
async def conversion_job_cancel(callback: CallbackQuery) -> None:
    if callback.from_user is not None:
        tool = callback.data.removeprefix("conv:cancel:")
        item = ACTIVE_CONVERSION_JOBS.pop((callback.from_user.id, tool), None)
        if item is not None:
            item[0].set()
    await callback.answer()


async def _conversion_retry(
    callback: CallbackQuery,
    state: FSMContext,
    session_factory: sessionmaker[Session],
    target_state: Any,
    prompt: str,
) -> None:
    if callback.from_user is None:
        return
    language = user_language(session_factory, callback.from_user.id)
    await state.set_state(target_state)
    await callback.answer()
    if isinstance(callback.message, Message):
        await callback.message.edit_text(prompt, reply_markup=cancel_menu(language))


async def _conversion_home(
    callback: CallbackQuery,
    state: FSMContext,
    session_factory: sessionmaker[Session],
) -> None:
    if callback.from_user is None:
        return
    from app.handlers.start import clear_state_and_file

    await clear_state_and_file(state)
    language = user_language(session_factory, callback.from_user.id)
    await callback.answer()
    if isinstance(callback.message, Message):
        await callback.message.edit_text(
            action_message(language, 3), reply_markup=main_menu(language)
        )


@router.callback_query(F.data == "session_tdata:retry")
async def session_tdata_retry(
    callback: CallbackQuery,
    state: FSMContext,
    session_factory: sessionmaker[Session],
) -> None:
    await _conversion_retry(
        callback,
        state,
        session_factory,
        ConvertSessionToTdata.waiting_for_file,
        SESSION_TO_TDATA_PROMPTS.get(
            user_language(session_factory, callback.from_user.id),
            SESSION_TO_TDATA_PROMPTS["en"],
        ),
    )


@router.callback_query(F.data == "session_tdata:home")
async def session_tdata_home(
    callback: CallbackQuery,
    state: FSMContext,
    session_factory: sessionmaker[Session],
) -> None:
    await _conversion_home(callback, state, session_factory)


@router.callback_query(F.data == "tdata_session:retry")
async def tdata_session_retry(
    callback: CallbackQuery,
    state: FSMContext,
    session_factory: sessionmaker[Session],
) -> None:
    await _conversion_retry(
        callback,
        state,
        session_factory,
        ConvertTdataToSession.waiting_for_file,
        TDATA_TO_SESSION_PROMPTS.get(
            user_language(session_factory, callback.from_user.id),
            TDATA_TO_SESSION_PROMPTS["en"],
        ),
    )


@router.callback_query(F.data == "tdata_session:home")
async def tdata_session_home(
    callback: CallbackQuery,
    state: FSMContext,
    session_factory: sessionmaker[Session],
) -> None:
    await _conversion_home(callback, state, session_factory)


@router.callback_query(F.data == "account_txt:retry")
async def account_txt_retry(
    callback: CallbackQuery,
    state: FSMContext,
    session_factory: sessionmaker[Session],
) -> None:
    await _conversion_retry(
        callback,
        state,
        session_factory,
        AccountToTxt.waiting_for_file,
        ACCOUNT_TO_TXT_PROMPTS.get(
            user_language(session_factory, callback.from_user.id),
            ACCOUNT_TO_TXT_PROMPTS["en"],
        ),
    )


@router.callback_query(F.data == "account_txt:home")
async def account_txt_home(
    callback: CallbackQuery,
    state: FSMContext,
    session_factory: sessionmaker[Session],
) -> None:
    await _conversion_home(callback, state, session_factory)


@router.callback_query(F.data == "session_json:retry")
async def session_json_retry(
    callback: CallbackQuery,
    state: FSMContext,
    session_factory: sessionmaker[Session],
) -> None:
    await _conversion_retry(
        callback,
        state,
        session_factory,
        ConvertSessionToJson.waiting_for_file,
        SESSION_TO_JSON_PROMPTS.get(
            user_language(session_factory, callback.from_user.id),
            SESSION_TO_JSON_PROMPTS["en"],
        ),
    )


@router.callback_query(F.data == "session_json:home")
async def session_json_home(
    callback: CallbackQuery,
    state: FSMContext,
    session_factory: sessionmaker[Session],
) -> None:
    await _conversion_home(callback, state, session_factory)


@router.message(AnalyzeFile.waiting_for_file)
async def analysis_requires_document(
    message: Message, state: FSMContext, session_factory: sessionmaker[Session]
) -> None:
    if message.from_user is None:
        return
    language = user_language(session_factory, message.from_user.id)
    state_data = await state.get_data()
    if state_data.get("check_contacts"):
        prompt = CHECK_CONTACTS_PROMPTS.get(language, CHECK_CONTACTS_PROMPTS["en"])
    elif state_data.get("session_check"):
        if state_data.get("live_spam_check"):
            prompt = SPAM_CHECK_PROMPTS.get(language, SPAM_CHECK_PROMPTS["en"])
        else:
            prompt = SESSION_CHECK_PROMPTS.get(language, SESSION_CHECK_PROMPTS["en"])
    else:
        prompt = ANALYZE_PROMPTS.get(language, ANALYZE_PROMPTS["en"])
    await message.answer(prompt, reply_markup=cancel_menu(language))


@router.callback_query(F.data == "tool:change_2fa")
async def request_change_2fa(
    callback: CallbackQuery,
    state: FSMContext,
    session_factory: sessionmaker[Session],
) -> None:
    language = user_language(session_factory, callback.from_user.id)
    await state.set_state(Change2FA.waiting_for_file)
    await callback.answer()
    if isinstance(callback.message, Message):
        await state.set_data({"flow_message_id": callback.message.message_id})
        await callback.message.edit_text(
            EmojiRegistry.enrich(
                CHANGE_2FA_PROMPTS.get(language, CHANGE_2FA_PROMPTS["en"])
            ),
            reply_markup=cancel_menu(language),
        )


@router.callback_query(F.data == "tool:disable_2fa")
async def request_disable_2fa(
    callback: CallbackQuery,
    state: FSMContext,
    session_factory: sessionmaker[Session],
) -> None:
    language = user_language(session_factory, callback.from_user.id)
    await state.set_state(Disable2FA.waiting_for_file)
    await callback.answer()
    if isinstance(callback.message, Message):
        await state.set_data({"flow_message_id": callback.message.message_id})
        await callback.message.edit_text(
            EmojiRegistry.enrich(
                DISABLE_2FA_PROMPTS.get(language, DISABLE_2FA_PROMPTS["en"])
            ),
            reply_markup=cancel_menu(language),
        )


@router.callback_query(F.data == "tool:reset_2fa")
async def request_reset_2fa(
    callback: CallbackQuery,
    state: FSMContext,
    session_factory: sessionmaker[Session],
) -> None:
    language = user_language(session_factory, callback.from_user.id)
    await state.set_state(Reset2FA.waiting_for_file)
    await callback.answer()
    if isinstance(callback.message, Message):
        await state.set_data({"flow_message_id": callback.message.message_id})
        await callback.message.edit_text(
            EmojiRegistry.enrich(
                RESET_2FA_PROMPTS.get(language, RESET_2FA_PROMPTS["en"])
            ),
            reply_markup=cancel_menu(language),
        )


@router.callback_query(F.data == "two_factor:noop")
async def two_factor_noop(callback: CallbackQuery) -> None:
    await callback.answer()


async def _edit_two_factor_flow(
    message: Message,
    bot: Bot,
    state: FSMContext,
    text: str,
    reply_markup: InlineKeyboardMarkup,
) -> Message:
    data = await state.get_data()
    flow_message_id = data.get("flow_message_id")
    if isinstance(flow_message_id, int):
        try:
            edited = await bot.edit_message_text(
                chat_id=message.chat.id,
                message_id=flow_message_id,
                text=text,
                reply_markup=reply_markup,
            )
            if isinstance(edited, Message):
                return edited
        except Exception as exc:  # noqa: BLE001
            LOGGER.debug("Could not edit 2FA flow message: %s", exc)
    answered = await message.answer(text, reply_markup=reply_markup)
    if isinstance(answered, Message):
        await state.update_data(flow_message_id=answered.message_id)
    return answered


async def _clear_two_factor_state(state: FSMContext) -> None:
    """Remove staged 2FA session files/dirs and clear the flow state."""
    data = await state.get_data()
    batch_dir = data.get("two_factor_batch_dir")
    if batch_dir:
        shutil.rmtree(str(batch_dir), ignore_errors=True)
    for stored in data.get("two_factor_session_files", []):
        Path(str(stored)).unlink(missing_ok=True)
    for key in ("source_path", "temp_file_path"):
        stored_path = data.get(key)
        if stored_path:
            Path(str(stored_path)).unlink(missing_ok=True)
    await state.clear()


@router.callback_query(F.data.startswith("two_factor:cancel:"))
async def cancel_two_factor_job(
    callback: CallbackQuery,
    state: FSMContext,
    session_factory: sessionmaker[Session],
) -> None:
    if callback.from_user is None or callback.data is None:
        return
    tool = callback.data.rsplit(":", 1)[-1]
    event = ACTIVE_2FA_JOBS.pop((callback.from_user.id, tool), None)
    if event is not None:
        event.set()
    await callback.answer()
    if isinstance(callback.message, Message):
        language = user_language(session_factory, callback.from_user.id)
        msgs_2fa = TWO_FACTOR_MESSAGES.get(language, TWO_FACTOR_MESSAGES["en"])
        await callback.message.edit_text(
            EmojiRegistry.enrich(msgs_2fa["cancelled"]),
            reply_markup=main_menu(language),
        )
    await _clear_two_factor_state(state)


def _two_factor_failure_details(result: TwoFactorResult, language: str) -> str:
    if not result.failure_reasons:
        return ""
    errors = TWO_FACTOR_ERRORS.get(language, TWO_FACTOR_ERRORS["en"])
    details = [
        errors.get(reason, TWO_FACTOR_ERRORS["en"].get(reason, reason))
        for reason in result.failure_reasons
    ]
    return "\n\n" + "\n".join(f"⚠️ {html.quote(detail)}" for detail in details)


def _two_factor_error_text(error: str, language: str) -> str:
    errors = TWO_FACTOR_ERRORS.get(language, TWO_FACTOR_ERRORS["en"])
    archive_errors = ARCHIVE_ERRORS.get(language, ARCHIVE_ERRORS["en"])
    return errors.get(error, archive_errors.get(error, error))


def _two_factor_account_prompt(
    data: dict[str, object], language: str, *, new_password: bool = False
) -> str:
    raw_files = data.get("two_factor_session_files")
    files = (
        [str(item) for item in raw_files]
        if isinstance(raw_files, (list, tuple))
        else []
    )
    raw_index = data.get("two_factor_index", 0)
    index = int(raw_index) if isinstance(raw_index, (int, str)) else 0
    templates = (
        TWO_FACTOR_ACCOUNT_NEW_PROMPT
        if new_password
        else TWO_FACTOR_ACCOUNT_CURRENT_PROMPT
    )
    template = templates.get(language, templates["en"])
    session_name = Path(files[index]).name if index < len(files) else "session"
    return template.format(
        current=index + 1,
        total=len(files),
        session=html.quote(session_name),
    )


async def _begin_two_factor_batch(
    source: Path,
    original_name: str,
    operation: Literal["changed", "disabled"],
    message: Message,
    bot: Bot,
    state: FSMContext,
    language: str,
) -> None:
    batch_dir = Path(tempfile.mkdtemp(prefix=f"ftgc_2fa_{operation}_batch_"))
    try:
        sessions = stage_two_factor_sessions(
            source, batch_dir, original_name=original_name
        )
        if not sessions:
            raise ValueError("no_sessions")
        await state.update_data(
            two_factor_batch_dir=str(batch_dir),
            two_factor_session_files=[str(path) for path in sessions],
            two_factor_index=0,
            two_factor_successful_indexes=[],
            two_factor_operation=operation,
            two_factor_force_zip=Path(original_name).suffix.lower() == ".zip",
            two_factor_busy=False,
            session_count=len(sessions),
            old_password=None,
        )
        if operation == "changed":
            await state.set_state(Change2FA.waiting_for_old_password)
        else:
            await state.set_state(Disable2FA.waiting_for_password)
        data = await state.get_data()
        await _edit_two_factor_flow(
            message,
            bot,
            state,
            EmojiRegistry.enrich(_two_factor_account_prompt(data, language)),
            cancel_menu(language),
        )
    except Exception:
        shutil.rmtree(batch_dir, ignore_errors=True)
        raise
    finally:
        source.unlink(missing_ok=True)


async def _finish_two_factor_batch(
    message: Message,
    bot: Bot,
    state: FSMContext,
    settings: Settings,
    language: str,
) -> None:
    data = await state.get_data()
    files = [Path(str(item)) for item in data.get("two_factor_session_files", [])]
    successful = {int(item) for item in data.get("two_factor_successful_indexes", [])}
    operation_raw = data.get("two_factor_operation")
    operation: Literal["changed", "disabled"] = (
        "disabled" if operation_raw == "disabled" else "changed"
    )
    batch_dir = Path(str(data.get("two_factor_batch_dir", "")))
    output_path: Path | None = None
    msgs = TWO_FACTOR_MESSAGES.get(language, TWO_FACTOR_MESSAGES["en"])
    try:
        result = package_two_factor_batch(
            files,
            successful,
            settings.storage_dir / "outbox",
            operation,
            force_zip=bool(data.get("two_factor_force_zip", False)),
        )
        output_path = result.output_path
        report = EmojiRegistry.enrich(
            msgs["done_change_disable"].format(
                success=result.success, failed=result.failed
            )
        )
        status = await _edit_two_factor_flow(
            message,
            bot,
            state,
            report,
            two_factor_result_menu(
                result.total, result.success, result.failed, language
            ),
        )
        if output_path and output_path.exists():
            await status.answer_document(
                FSInputFile(output_path, filename=output_path.name)
            )
    finally:
        if output_path and output_path.exists():
            output_path.unlink(missing_ok=True)
        if str(batch_dir):
            shutil.rmtree(batch_dir, ignore_errors=True)
        await _clear_two_factor_state(state)


async def _advance_two_factor_batch(
    message: Message,
    bot: Bot,
    state: FSMContext,
    settings: Settings,
    language: str,
    *,
    succeeded: bool,
) -> None:
    data = await state.get_data()
    index = int(data.get("two_factor_index", 0))
    files = [str(item) for item in data.get("two_factor_session_files", [])]
    successful = [int(item) for item in data.get("two_factor_successful_indexes", [])]
    if succeeded:
        successful.append(index)
    next_index = index + 1
    await state.update_data(
        two_factor_index=next_index,
        two_factor_successful_indexes=successful,
        old_password=None,
    )
    if next_index >= len(files):
        await _finish_two_factor_batch(message, bot, state, settings, language)
        return

    operation = data.get("two_factor_operation")
    cancel_tool = "change" if operation == "changed" else "disable"
    if operation == "disabled":
        await state.set_state(Disable2FA.waiting_for_password)
    else:
        await state.set_state(Change2FA.waiting_for_old_password)
    updated = await state.get_data()
    await _edit_two_factor_flow(
        message,
        bot,
        state,
        EmojiRegistry.enrich(_two_factor_account_prompt(updated, language)),
        two_factor_cancel_menu(language, cancel_tool),
    )


@router.message(Change2FA.waiting_for_file, F.document)
async def receive_change_2fa_file(
    message: Message,
    bot: Bot,
    state: FSMContext,
    settings: Settings,
    session_factory: sessionmaker[Session],
) -> None:
    if message.from_user is None or message.document is None:
        return
    language = user_language(session_factory, message.from_user.id)
    msgs_2fa = TWO_FACTOR_MESSAGES.get(language, TWO_FACTOR_MESSAGES["en"])
    path: Path | None = None
    try:
        path, name = await download_document(message, bot, settings, language)
        sessions = await inspect_mergeable_sessions(path)
        if not sessions:
            path.unlink(missing_ok=True)
            await _clear_two_factor_state(state)
            await message.answer(
                EmojiRegistry.enrich(msgs_2fa["no_sessions"]),
                reply_markup=main_menu(language),
            )
            return
        await _begin_two_factor_batch(
            path, name, "changed", message, bot, state, language
        )
        path = None
    except Exception as exc:  # noqa: BLE001
        if path is not None:
            path.unlink(missing_ok=True)
        error = _two_factor_error_text(str(exc), language)
        await message.answer(
            EmojiRegistry.enrich(f"❌ {html.quote(error)}"),
            reply_markup=cancel_menu(language),
        )


@router.message(Change2FA.waiting_for_old_password, F.text)
async def receive_change_2fa_old_password(
    message: Message,
    bot: Bot,
    state: FSMContext,
    session_factory: sessionmaker[Session],
) -> None:
    if message.from_user is None or not message.text:
        return
    language = user_language(session_factory, message.from_user.id)
    msgs_2fa = TWO_FACTOR_MESSAGES.get(language, TWO_FACTOR_MESSAGES["en"])
    old_password = message.text
    with suppress(Exception):
        await message.delete()
    if not old_password:
        await message.answer(
            EmojiRegistry.enrich(msgs_2fa["password_required"]),
            reply_markup=cancel_menu(language),
        )
        return
    await state.update_data(old_password=old_password)
    await state.set_state(Change2FA.waiting_for_new_password)
    data = await state.get_data()
    await _edit_two_factor_flow(
        message,
        bot,
        state,
        EmojiRegistry.enrich(_two_factor_account_prompt(data, language, new_password=True)),
        cancel_menu(language),
    )


@router.message(Change2FA.waiting_for_new_password, F.text)
async def receive_change_2fa_new_password(
    message: Message,
    bot: Bot,
    state: FSMContext,
    settings: Settings,
    session_factory: sessionmaker[Session],
) -> None:
    if message.from_user is None or not message.text:
        return
    language = user_language(session_factory, message.from_user.id)
    msgs_2fa = TWO_FACTOR_MESSAGES.get(language, TWO_FACTOR_MESSAGES["en"])
    new_password = message.text
    with suppress(Exception):
        await message.delete()
    if not new_password:
        await message.answer(
            EmojiRegistry.enrich(msgs_2fa["password_required"]),
            reply_markup=cancel_menu(language),
        )
        return
    data = await state.get_data()
    if data.get("two_factor_busy"):
        return
    old_password = data.get("old_password")
    await state.update_data(old_password=None, two_factor_busy=True)
    files = [Path(str(item)) for item in data.get("two_factor_session_files", [])]
    index = int(data.get("two_factor_index", 0))
    if index >= len(files) or not isinstance(old_password, str) or not old_password:
        await _clear_two_factor_state(state)
        await message.answer(
            EmojiRegistry.enrich(msgs_2fa["no_sessions"]),
            reply_markup=main_menu(language),
        )
        return
    await _edit_two_factor_flow(
        message,
        bot,
        state,
        EmojiRegistry.enrich(msgs_2fa["processing"]),
        two_factor_cancel_menu(language, "change"),
    )
    cancel_event = asyncio.Event()
    ACTIVE_2FA_JOBS[(message.from_user.id, "change")] = cancel_event
    try:
        succeeded = await edit_two_factor_session(
            files[index],
            settings.api_credential_list,
            current_password=old_password,
            new_password=new_password,
            cancel_event=cancel_event,
        )
        if cancel_event.is_set():
            return
        await _advance_two_factor_batch(
            message,
            bot,
            state,
            settings,
            language,
            succeeded=succeeded,
        )
    except Exception:
        LOGGER.exception("2FA change failed for user %s", message.from_user.id)
        await _edit_two_factor_flow(
            message,
            bot,
            state,
            EmojiRegistry.enrich(msgs_2fa["request_failed"]),
            reply_markup=main_menu(language),
        )
    finally:
        ACTIVE_2FA_JOBS.pop((message.from_user.id, "change"), None)


@router.message(Disable2FA.waiting_for_file, F.document)
async def receive_disable_2fa_file(
    message: Message,
    bot: Bot,
    state: FSMContext,
    settings: Settings,
    session_factory: sessionmaker[Session],
) -> None:
    if message.from_user is None or message.document is None:
        return
    language = user_language(session_factory, message.from_user.id)
    msgs_2fa = TWO_FACTOR_MESSAGES.get(language, TWO_FACTOR_MESSAGES["en"])
    path: Path | None = None
    try:
        path, name = await download_document(message, bot, settings, language)
        sessions = await inspect_mergeable_sessions(path)
        if not sessions:
            path.unlink(missing_ok=True)
            await _clear_two_factor_state(state)
            await message.answer(
                EmojiRegistry.enrich(msgs_2fa["no_sessions"]),
                reply_markup=main_menu(language),
            )
            return
        await _begin_two_factor_batch(
            path, name, "disabled", message, bot, state, language
        )
        path = None
    except Exception as exc:  # noqa: BLE001
        if path is not None:
            path.unlink(missing_ok=True)
        error = _two_factor_error_text(str(exc), language)
        await message.answer(
            EmojiRegistry.enrich(f"❌ {html.quote(error)}"),
            reply_markup=cancel_menu(language),
        )


@router.message(Disable2FA.waiting_for_password, F.text)
async def receive_disable_2fa_password(
    message: Message,
    bot: Bot,
    state: FSMContext,
    settings: Settings,
    session_factory: sessionmaker[Session],
) -> None:
    if message.from_user is None or not message.text:
        return
    language = user_language(session_factory, message.from_user.id)
    msgs_2fa = TWO_FACTOR_MESSAGES.get(language, TWO_FACTOR_MESSAGES["en"])
    current_password = message.text
    with suppress(Exception):
        await message.delete()
    if not current_password:
        await message.answer(
            EmojiRegistry.enrich(msgs_2fa["password_required"]),
            reply_markup=cancel_menu(language),
        )
        return
    data = await state.get_data()
    if data.get("two_factor_busy"):
        return
    await state.update_data(two_factor_busy=True)
    files = [Path(str(item)) for item in data.get("two_factor_session_files", [])]
    index = int(data.get("two_factor_index", 0))
    if index >= len(files):
        await _clear_two_factor_state(state)
        await message.answer(
            EmojiRegistry.enrich(msgs_2fa["no_sessions"]),
            reply_markup=main_menu(language),
        )
        return
    await _edit_two_factor_flow(
        message,
        bot,
        state,
        EmojiRegistry.enrich(msgs_2fa["processing"]),
        two_factor_cancel_menu(language, "disable"),
    )
    cancel_event = asyncio.Event()
    ACTIVE_2FA_JOBS[(message.from_user.id, "disable")] = cancel_event
    try:
        succeeded = await edit_two_factor_session(
            files[index],
            settings.api_credential_list,
            current_password=current_password,
            cancel_event=cancel_event,
        )
        if cancel_event.is_set():
            return
        await _advance_two_factor_batch(
            message,
            bot,
            state,
            settings,
            language,
            succeeded=succeeded,
        )
    except Exception:
        LOGGER.exception("2FA disable failed for user %s", message.from_user.id)
        await _edit_two_factor_flow(
            message,
            bot,
            state,
            EmojiRegistry.enrich(msgs_2fa["request_failed"]),
            reply_markup=main_menu(language),
        )
    finally:
        ACTIVE_2FA_JOBS.pop((message.from_user.id, "disable"), None)


@router.message(Reset2FA.waiting_for_file, F.document)
async def receive_reset_2fa_file(
    message: Message,
    bot: Bot,
    state: FSMContext,
    settings: Settings,
    session_factory: sessionmaker[Session],
) -> None:
    if message.from_user is None or message.document is None:
        return
    language = user_language(session_factory, message.from_user.id)
    msgs_2fa = TWO_FACTOR_MESSAGES.get(language, TWO_FACTOR_MESSAGES["en"])
    path: Path | None = None
    try:
        path, name = await download_document(message, bot, settings, language)
        sessions = await inspect_mergeable_sessions(path)
        if not sessions:
            path.unlink(missing_ok=True)
            await _clear_two_factor_state(state)
            await message.answer(
                EmojiRegistry.enrich(msgs_2fa["no_sessions"]),
                reply_markup=main_menu(language),
            )
            return

        status = await _edit_two_factor_flow(
            message,
            bot,
            state,
            EmojiRegistry.enrich(msgs_2fa["processing"]),
            two_factor_cancel_menu(language, "reset"),
        )
        cancel_event = asyncio.Event()
        ACTIVE_2FA_JOBS[(message.from_user.id, "reset")] = cancel_event
        out_res: Path | None = None
        try:
            res_2fa = await process_reset_2fa(
                path,
                output_dir=settings.storage_dir / "outbox",
                credentials=settings.api_credential_list,
                original_name=name,
                cancel_event=cancel_event,
            )
            if cancel_event.is_set():
                return
            out_res = res_2fa.output_path
            report = EmojiRegistry.enrich(
                msgs_2fa["done_reset"].format(
                    success=res_2fa.success,
                    pending=res_2fa.pending,
                    failed=res_2fa.failed,
                )
            )
            report += _two_factor_failure_details(res_2fa, language)
            await status.edit_text(
                report,
                reply_markup=two_factor_result_menu(
                    res_2fa.total,
                    res_2fa.success,
                    res_2fa.failed,
                    language,
                    pending=res_2fa.pending,
                ),
            )
            if out_res and out_res.exists():
                suffix = ".zip" if res_2fa.is_zip else ".session"
                await message.answer_document(
                    FSInputFile(
                        out_res,
                        filename=f"2FA_Reset_{res_2fa.success}{suffix}",
                    )
                )
        finally:
            if out_res and out_res.exists():
                out_res.unlink(missing_ok=True)
    except Exception as exc:  # noqa: BLE001
        error = _two_factor_error_text(str(exc), language)
        await message.answer(
            EmojiRegistry.enrich(f"❌ {html.quote(error)}"),
            reply_markup=cancel_menu(language),
        )
    finally:
        ACTIVE_2FA_JOBS.pop((message.from_user.id, "reset"), None)
        if path is not None:
            path.unlink(missing_ok=True)
        await _clear_two_factor_state(state)


@router.callback_query(F.data == "tool:clean_chat")
async def request_clean_chat(
    callback: CallbackQuery,
    state: FSMContext,
    session_factory: sessionmaker[Session],
) -> None:
    language = user_language(session_factory, callback.from_user.id)
    await state.set_state(CleanChat.waiting_for_file)
    await callback.answer()
    if isinstance(callback.message, Message):
        await callback.message.edit_text(
            ENTER_CLEAN_CHAT_PROMPT.get(language, ENTER_CLEAN_CHAT_PROMPT["en"]),
            reply_markup=cancel_menu(language),
        )


@router.message(CleanChat.waiting_for_file, F.document)
async def receive_clean_chat_file(
    message: Message,
    bot: Bot,
    state: FSMContext,
    settings: Settings,
    session_factory: sessionmaker[Session],
) -> None:
    if message.from_user is None or message.document is None:
        return
    language = user_language(session_factory, message.from_user.id)
    msgs_clean = CLEAN_CHAT_MESSAGES.get(language, CLEAN_CHAT_MESSAGES["en"])
    path: Path | None = None
    try:
        path, name = await download_document(message, bot, settings, language)
        sessions = await inspect_mergeable_sessions(path)
        if not sessions:
            path.unlink(missing_ok=True)
            await state.clear()
            await message.answer(
                msgs_clean["no_sessions"], reply_markup=main_menu(language)
            )
            return

        await state.set_state(CleanChat.waiting_for_selection)
        await state.update_data(
            temp_file_path=str(path),
            original_name=name,
            session_count=len(sessions),
            clean_chat_categories=[],
        )
        prompt_fmt = CLEAN_CHAT_MODE_PROMPT.get(language, CLEAN_CHAT_MODE_PROMPT["en"])
        await message.answer(
            prompt_fmt.format(count=len(sessions)),
            reply_markup=clean_chat_choice_menu(language, selected=()),
        )
    except Exception as exc:  # noqa: BLE001
        if path is not None:
            path.unlink(missing_ok=True)
        archive_errors = ARCHIVE_ERRORS.get(language, ARCHIVE_ERRORS["en"])
        error = archive_errors.get(str(exc), str(exc))
        await message.answer(
            f"❌ {html.quote(error)}", reply_markup=cancel_menu(language)
        )
        await state.clear()


@router.callback_query(
    CleanChat.waiting_for_selection, F.data.startswith("clean_chat_toggle:")
)
async def toggle_clean_chat_category(
    callback: CallbackQuery,
    state: FSMContext,
    session_factory: sessionmaker[Session],
) -> None:
    if callback.data is None:
        return
    language = user_language(session_factory, callback.from_user.id)
    category = callback.data.split(":", 1)[1]
    if category != "all" and category not in CLEAN_CHAT_CATEGORIES:
        await callback.answer(show_alert=True)
        return

    data = await state.get_data()
    selected = {
        str(item)
        for item in data.get("clean_chat_categories", [])
        if str(item) in CLEAN_CHAT_CATEGORIES
    }
    if category == "all":
        selected = (
            set()
            if selected == set(CLEAN_CHAT_CATEGORIES)
            else set(CLEAN_CHAT_CATEGORIES)
        )
    elif category in selected:
        selected.remove(category)
    else:
        selected.add(category)

    await state.update_data(clean_chat_categories=sorted(selected))
    await callback.answer()
    if isinstance(callback.message, Message):
        await callback.message.edit_reply_markup(
            reply_markup=clean_chat_choice_menu(language, selected=selected)
        )


@router.callback_query(CleanChat.waiting_for_selection, F.data == "clean_chat_confirm")
async def confirm_clean_chat_selection(
    callback: CallbackQuery,
    state: FSMContext,
    settings: Settings,
    session_factory: sessionmaker[Session],
) -> None:
    if callback.data is None:
        return
    language = user_language(session_factory, callback.from_user.id)
    msgs_clean = CLEAN_CHAT_MESSAGES.get(language, CLEAN_CHAT_MESSAGES["en"])
    selection_actions = CLEAN_CHAT_SELECTION_ACTIONS.get(
        language, CLEAN_CHAT_SELECTION_ACTIONS["en"]
    )
    data = await state.get_data()
    selected = {
        str(item)
        for item in data.get("clean_chat_categories", [])
        if str(item) in CLEAN_CHAT_CATEGORIES
    }
    if not selected:
        await callback.answer(selection_actions["select_one"], show_alert=True)
        return

    temp_path_str = data.get("temp_file_path")
    original_name = data.get("original_name")

    if not temp_path_str:
        await state.clear()
        await callback.answer()
        if isinstance(callback.message, Message):
            await callback.message.edit_text(
                msgs_clean["no_sessions"], reply_markup=main_menu(language)
            )
        return

    temp_path = Path(temp_path_str)
    if not temp_path.exists():
        await state.clear()
        await callback.answer()
        if isinstance(callback.message, Message):
            await callback.message.edit_text(
                msgs_clean["no_sessions"], reply_markup=main_menu(language)
            )
        return

    await callback.answer()
    status_msg = None
    if isinstance(callback.message, Message):
        status_msg = await callback.message.edit_text(msgs_clean["processing"])

    out_res: Path | None = None
    try:
        user_proxy = resolve_user_proxy(session_factory, callback.from_user.id)
        res_cln = await process_clean_chat(
            temp_path,
            output_dir=settings.storage_dir / "outbox",
            mode=sorted(selected),
            credentials=settings.api_credential_list,
            original_name=original_name,
            proxy=user_proxy,
            concurrency=settings.clean_chat_concurrency,
            flood_ceiling=settings.clean_chat_flood_ceiling,
        )
        out_res = res_cln.output_path
        if res_cln.cleaned == 0:
            report = msgs_clean["failed_report"].format(failed=res_cln.failed)
        else:
            report = msgs_clean["done"].format(
                success=res_cln.cleaned, failed=res_cln.failed
            )
        if isinstance(status_msg, Message):
            await status_msg.edit_text(
                report,
                reply_markup=clean_chat_result_menu(
                    res_cln.total, res_cln.cleaned, res_cln.failed, language
                ),
            )
        if out_res and out_res.exists() and isinstance(callback.message, Message):
            await callback.message.answer_document(
                FSInputFile(out_res, filename=out_res.name)
            )
    except Exception:
        LOGGER.exception("Clean chat error for user %s", callback.from_user.id)
        if isinstance(status_msg, Message):
            await status_msg.edit_text(
                msgs_clean["request_failed"], reply_markup=main_menu(language)
            )
    finally:
        if out_res and out_res.exists():
            out_res.unlink(missing_ok=True)
        if temp_path.exists():
            temp_path.unlink(missing_ok=True)
        await state.clear()


@router.callback_query(F.data == "clean_chat:noop")
async def clean_chat_noop(callback: CallbackQuery) -> None:
    await callback.answer()


@router.callback_query(F.data == "tool:delete_contact")
async def request_delete_contact(
    callback: CallbackQuery,
    state: FSMContext,
    session_factory: sessionmaker[Session],
) -> None:
    language = user_language(session_factory, callback.from_user.id)
    await state.set_state(DeleteContact.waiting_for_file)
    await callback.answer()
    if isinstance(callback.message, Message):
        await callback.message.edit_text(
            ENTER_DELETE_CONTACT_PROMPT.get(
                language, ENTER_DELETE_CONTACT_PROMPT["en"]
            ),
            reply_markup=cancel_menu(language),
        )


@router.message(DeleteContact.waiting_for_file, F.document)
async def receive_delete_contact_file(
    message: Message,
    bot: Bot,
    state: FSMContext,
    settings: Settings,
    session_factory: sessionmaker[Session],
) -> None:
    if message.from_user is None or message.document is None:
        return
    language = user_language(session_factory, message.from_user.id)
    msgs_del = DELETE_CONTACT_MESSAGES.get(language, DELETE_CONTACT_MESSAGES["en"])
    path: Path | None = None
    try:
        path, name = await download_document(message, bot, settings, language)
        sessions = await inspect_mergeable_sessions(path)
        if not sessions:
            path.unlink(missing_ok=True)
            await state.clear()
            await message.answer(
                msgs_del["no_sessions"], reply_markup=main_menu(language)
            )
            return

        status = await message.answer(msgs_del["fetching"])
        contacts = await fetch_input_contacts(
            path,
            settings.api_credential_list,
            original_name=name,
        )

        if not contacts:
            path.unlink(missing_ok=True)
            await state.clear()
            await status.edit_text(
                msgs_del["no_contacts"], reply_markup=main_menu(language)
            )
            return

        contact_dicts = [c.to_dict() for c in contacts]
        await state.set_state(DeleteContact.selecting_contacts)
        await state.update_data(
            temp_file_path=str(path),
            original_name=name,
            contacts=contact_dicts,
            selected_ids=[],
            page=0,
        )

        fmt = DELETE_CONTACT_SELECT_PROMPT.get(
            language, DELETE_CONTACT_SELECT_PROMPT["en"]
        )
        await status.edit_text(
            fmt.format(count=len(contacts)),
            reply_markup=delete_contact_selection_menu(
                contact_dicts, set(), page=0, language=language
            ),
        )
    except Exception as exc:  # noqa: BLE001
        if path is not None:
            path.unlink(missing_ok=True)
        archive_errors = ARCHIVE_ERRORS.get(language, ARCHIVE_ERRORS["en"])
        error = archive_errors.get(str(exc), str(exc))
        await message.answer(
            f"❌ {html.quote(error)}", reply_markup=cancel_menu(language)
        )
        await state.clear()


@router.callback_query(
    DeleteContact.selecting_contacts, F.data.startswith("del_cnt_toggle:")
)
async def toggle_delete_contact(
    callback: CallbackQuery,
    state: FSMContext,
    session_factory: sessionmaker[Session],
) -> None:
    if callback.data is None or not isinstance(callback.message, Message):
        return
    language = user_language(session_factory, callback.from_user.id)
    uid = int(callback.data.split(":", 1)[1])
    data = await state.get_data()
    contacts = data.get("contacts", [])
    selected_ids = set(data.get("selected_ids", []))
    page = data.get("page", 0)
    valid_ids = {int(contact["user_id"]) for contact in contacts}
    if uid not in valid_ids:
        await callback.answer()
        return

    if uid in selected_ids:
        selected_ids.remove(uid)
    else:
        selected_ids.add(uid)

    await state.update_data(selected_ids=list(selected_ids))
    await callback.answer()
    fmt = DELETE_CONTACT_SELECT_PROMPT.get(language, DELETE_CONTACT_SELECT_PROMPT["en"])
    await callback.message.edit_text(
        fmt.format(count=len(contacts)),
        reply_markup=delete_contact_selection_menu(
            contacts, selected_ids, page=page, language=language
        ),
    )


@router.callback_query(
    DeleteContact.selecting_contacts, F.data.startswith("del_cnt_page:")
)
async def navigate_delete_contact_page(
    callback: CallbackQuery,
    state: FSMContext,
    session_factory: sessionmaker[Session],
) -> None:
    if callback.data is None or not isinstance(callback.message, Message):
        return
    language = user_language(session_factory, callback.from_user.id)
    target_page = int(callback.data.split(":", 1)[1])
    data = await state.get_data()
    contacts = data.get("contacts", [])
    selected_ids = set(data.get("selected_ids", []))

    await state.update_data(page=target_page)
    await callback.answer()
    fmt = DELETE_CONTACT_SELECT_PROMPT.get(language, DELETE_CONTACT_SELECT_PROMPT["en"])
    await callback.message.edit_text(
        fmt.format(count=len(contacts)),
        reply_markup=delete_contact_selection_menu(
            contacts, selected_ids, page=target_page, language=language
        ),
    )


@router.callback_query(
    DeleteContact.selecting_contacts, F.data.startswith("del_cnt_action:")
)
async def action_delete_contact(
    callback: CallbackQuery,
    state: FSMContext,
    settings: Settings,
    session_factory: sessionmaker[Session],
) -> None:
    if callback.data is None or not isinstance(callback.message, Message):
        return
    language = user_language(session_factory, callback.from_user.id)
    msgs_del = DELETE_CONTACT_MESSAGES.get(language, DELETE_CONTACT_MESSAGES["en"])
    action = callback.data.split(":", 1)[1]
    data = await state.get_data()
    contacts = data.get("contacts", [])
    selected_ids = set(data.get("selected_ids", []))
    page = data.get("page", 0)

    if action == "noop_empty":
        await callback.answer(msgs_del["select_at_least_one"], show_alert=True)
        return

    if action == "select_all":
        all_ids = {c["user_id"] for c in contacts}
        await state.update_data(selected_ids=list(all_ids))
        await callback.answer()
        fmt = DELETE_CONTACT_SELECT_PROMPT.get(
            language, DELETE_CONTACT_SELECT_PROMPT["en"]
        )
        await callback.message.edit_text(
            fmt.format(count=len(contacts)),
            reply_markup=delete_contact_selection_menu(
                contacts, all_ids, page=page, language=language
            ),
        )
        return

    if action == "deselect_all":
        await state.update_data(selected_ids=[])
        await callback.answer()
        fmt = DELETE_CONTACT_SELECT_PROMPT.get(
            language, DELETE_CONTACT_SELECT_PROMPT["en"]
        )
        await callback.message.edit_text(
            fmt.format(count=len(contacts)),
            reply_markup=delete_contact_selection_menu(
                contacts, set(), page=page, language=language
            ),
        )
        return

    if action == "confirm":
        valid_ids = {int(contact["user_id"]) for contact in contacts}
        selected_ids &= valid_ids
        if not selected_ids:
            await callback.answer(msgs_del["select_at_least_one"], show_alert=True)
            return

        temp_path_str = data.get("temp_file_path")
        original_name = data.get("original_name")

        if not temp_path_str:
            await state.clear()
            await callback.answer()
            await callback.message.edit_text(
                msgs_del["no_sessions"], reply_markup=main_menu(language)
            )
            return

        temp_path = Path(temp_path_str)
        if not temp_path.exists():
            await state.clear()
            await callback.answer()
            await callback.message.edit_text(
                msgs_del["no_sessions"], reply_markup=main_menu(language)
            )
            return

        await callback.answer()
        status_msg = await callback.message.edit_text(msgs_del["processing"])
        out_res: Path | None = None
        try:
            res_del = await process_delete_contacts(
                temp_path,
                output_dir=settings.storage_dir / "outbox",
                credentials=settings.api_credential_list,
                target_user_ids=list(selected_ids),
                original_name=original_name,
            )
            out_res = res_del.output_path
            if res_del.deleted == 0:
                report = msgs_del["failed_report"].format(failed=res_del.failed)
            else:
                report = msgs_del["done"].format(
                    success=res_del.deleted, failed=res_del.failed
                )
            if isinstance(status_msg, Message):
                await status_msg.edit_text(
                    report,
                    reply_markup=delete_contact_result_menu(
                        res_del.total, res_del.deleted, res_del.failed, language
                    ),
                )
            if out_res and out_res.exists() and isinstance(callback.message, Message):
                await callback.message.answer_document(
                    FSInputFile(out_res, filename=out_res.name)
                )
        except Exception:
            LOGGER.exception("Delete contact error for user %s", callback.from_user.id)
            if isinstance(status_msg, Message):
                await status_msg.edit_text(
                    msgs_del["request_failed"], reply_markup=main_menu(language)
                )
        finally:
            if out_res and out_res.exists():
                out_res.unlink(missing_ok=True)
            if temp_path.exists():
                temp_path.unlink(missing_ok=True)
            await state.clear()


@router.callback_query(F.data == "del_cnt:noop")
async def delete_contact_noop(callback: CallbackQuery) -> None:
    await callback.answer()


async def _render_profile_setup_current_account(
    target_msg: Message,
    state: FSMContext,
    settings: Settings,
    language: str,
) -> None:
    data = await state.get_data()
    temp_dir_str = data.get("temp_dir")
    session_files_str = data.get("session_files", [])
    current_index = data.get("current_index", 0)
    modified_count = data.get("modified_count", 0)
    skipped_count = data.get("skipped_count", 0)
    failed_count = data.get("failed_count", 0)
    original_name = data.get("original_name")
    pending = data.get("pending", {})

    msgs_prof = PROFILE_SETUP_MESSAGES.get(language, PROFILE_SETUP_MESSAGES["en"])

    if not temp_dir_str or not session_files_str:
        await state.clear()
        await target_msg.edit_text(
            msgs_prof["no_sessions"], reply_markup=main_menu(language)
        )
        return

    session_files = [Path(p) for p in session_files_str]
    total = len(session_files)

    if current_index >= total:
        outbox_dir = settings.storage_dir / "outbox"
        res = package_profile_setup_results(
            session_files,
            outbox_dir,
            modified_count,
            skipped_count,
            failed_count,
            original_name=original_name,
        )
        if res.modified == 0 and res.skipped == 0:
            report = msgs_prof["failed_report"].format(failed=res.failed)
        else:
            report = msgs_prof["done"].format(
                modified=res.modified, skipped=res.skipped, failed=res.failed
            )
        await target_msg.edit_text(
            report,
            reply_markup=profile_setup_result_menu(
                res.total, res.modified, res.skipped, res.failed, language
            ),
        )
        if res.output_path and res.output_path.exists():
            await target_msg.answer_document(
                FSInputFile(res.output_path, filename=res.output_path.name)
            )
            res.output_path.unlink(missing_ok=True)

        temp_dir = Path(temp_dir_str)
        if temp_dir.exists():
            shutil.rmtree(temp_dir, ignore_errors=True)
        await state.clear()
        return

    cur_file = session_files[current_index]
    info = await fetch_account_profile(cur_file, settings.api_credential_list)

    if info is None:
        await state.update_data(
            current_index=current_index + 1,
            failed_count=failed_count + 1,
            pending={},
        )
        await _render_profile_setup_current_account(
            target_msg, state, settings, language
        )
        return

    identifier = info.phone if info.phone else cur_file.name
    first_name = info.first_name if info.first_name else "(None)"
    last_name = info.last_name if info.last_name else "(None)"
    username = f"@{info.username}" if info.username else "(None)"
    about = info.about if info.about else "(None)"

    p_first = (
        f"➡️ <i>({pending['first_name']})</i>"
        if pending.get("first_name") is not None
        else ""
    )
    p_last = (
        f"➡️ <i>({pending['last_name']})</i>"
        if pending.get("last_name") is not None
        else ""
    )
    p_username = (
        f"➡️ <i>(@{pending['username'].lstrip('@')})</i>"
        if pending.get("username") is not None
        else ""
    )
    p_about = (
        f"➡️ <i>({pending['about']})</i>" if pending.get("about") is not None else ""
    )

    photo_status = (
        msgs_prof["photo_pending"]
        if pending.get("photo_path")
        else msgs_prof["photo_none"]
    )

    fmt = PROFILE_SETUP_ACCOUNT_PROMPT.get(language, PROFILE_SETUP_ACCOUNT_PROMPT["en"])
    prompt_text = fmt.format(
        current=current_index + 1,
        total=total,
        identifier=html.quote(identifier),
        first_name=html.quote(first_name),
        last_name=html.quote(last_name),
        username=html.quote(username),
        about=html.quote(about),
        pending_first=p_first,
        pending_last=p_last,
        pending_username=p_username,
        pending_about=p_about,
        photo_status=photo_status,
    )

    await target_msg.edit_text(
        prompt_text, reply_markup=profile_setup_account_menu(language)
    )


@router.callback_query(F.data == "tool:profile_setup")
async def request_profile_setup(
    callback: CallbackQuery,
    state: FSMContext,
    session_factory: sessionmaker[Session],
) -> None:
    language = user_language(session_factory, callback.from_user.id)
    await state.set_state(ProfileSetup.waiting_for_file)
    await callback.answer()
    if isinstance(callback.message, Message):
        await callback.message.edit_text(
            ENTER_PROFILE_SETUP_PROMPT.get(language, ENTER_PROFILE_SETUP_PROMPT["en"]),
            reply_markup=cancel_menu(language),
        )


@router.message(ProfileSetup.waiting_for_file, F.document)
async def receive_profile_setup_file(
    message: Message,
    bot: Bot,
    state: FSMContext,
    settings: Settings,
    session_factory: sessionmaker[Session],
) -> None:
    if message.from_user is None or message.document is None:
        return
    language = user_language(session_factory, message.from_user.id)
    msgs_prof = PROFILE_SETUP_MESSAGES.get(language, PROFILE_SETUP_MESSAGES["en"])
    path: Path | None = None
    try:
        path, name = await download_document(message, bot, settings, language)
        sessions = await inspect_mergeable_sessions(path)
        if not sessions:
            path.unlink(missing_ok=True)
            await state.clear()
            await message.answer(
                msgs_prof["no_sessions"], reply_markup=main_menu(language)
            )
            return

        status = await message.answer(msgs_prof["fetching"])

        temp_dir = Path(tempfile.mkdtemp(prefix="ftgc_prof_dir_"))
        extracted_files: list[Path] = []
        if path.suffix.lower() == ".zip":
            extracted_files = extract_zip_sessions_safe(path, temp_dir)
        else:
            dest = temp_dir / path.name
            shutil.copy2(path, dest)
            extracted_files = [dest]

        path.unlink(missing_ok=True)

        if not extracted_files:
            shutil.rmtree(temp_dir, ignore_errors=True)
            await state.clear()
            await status.edit_text(
                msgs_prof["no_sessions"], reply_markup=main_menu(language)
            )
            return

        await state.set_state(ProfileSetup.managing_account)
        await state.update_data(
            temp_dir=str(temp_dir),
            session_files=[str(f) for f in extracted_files],
            current_index=0,
            modified_count=0,
            skipped_count=0,
            failed_count=0,
            original_name=name,
            pending={},
        )

        await _render_profile_setup_current_account(status, state, settings, language)
    except Exception as exc:  # noqa: BLE001
        if path is not None and path.exists():
            path.unlink(missing_ok=True)
        archive_errors = ARCHIVE_ERRORS.get(language, ARCHIVE_ERRORS["en"])
        error = archive_errors.get(str(exc), str(exc))
        await message.answer(
            f"❌ {html.quote(error)}", reply_markup=cancel_menu(language)
        )
        await state.clear()


@router.callback_query(ProfileSetup.managing_account, F.data == "prof_setup:edit_name")
async def prompt_profile_setup_name(
    callback: CallbackQuery,
    state: FSMContext,
    session_factory: sessionmaker[Session],
) -> None:
    if not isinstance(callback.message, Message):
        return
    language = user_language(session_factory, callback.from_user.id)
    await state.set_state(ProfileSetup.waiting_for_name)
    await callback.answer()
    await callback.message.edit_text(
        PROFILE_SETUP_NAME_PROMPT.get(language, PROFILE_SETUP_NAME_PROMPT["en"]),
        reply_markup=cancel_menu(language),
    )


@router.message(ProfileSetup.waiting_for_name, F.text)
async def receive_profile_setup_name(
    message: Message,
    state: FSMContext,
    settings: Settings,
    session_factory: sessionmaker[Session],
) -> None:
    if message.from_user is None or message.text is None:
        return
    language = user_language(session_factory, message.from_user.id)
    parts = message.text.strip().split(maxsplit=1)
    first_name = parts[0]
    last_name = parts[1] if len(parts) > 1 else ""

    data = await state.get_data()
    pending = data.get("pending", {})
    pending["first_name"] = first_name
    pending["last_name"] = last_name

    await state.set_state(ProfileSetup.managing_account)
    await state.update_data(pending=pending)

    msgs_prof = PROFILE_SETUP_MESSAGES.get(language, PROFILE_SETUP_MESSAGES["en"])
    status = await message.answer(msgs_prof["fetching"])
    await _render_profile_setup_current_account(status, state, settings, language)


@router.callback_query(
    ProfileSetup.managing_account, F.data == "prof_setup:edit_username"
)
async def prompt_profile_setup_username(
    callback: CallbackQuery,
    state: FSMContext,
    session_factory: sessionmaker[Session],
) -> None:
    if not isinstance(callback.message, Message):
        return
    language = user_language(session_factory, callback.from_user.id)
    await state.set_state(ProfileSetup.waiting_for_username)
    await callback.answer()
    await callback.message.edit_text(
        PROFILE_SETUP_USERNAME_PROMPT.get(
            language, PROFILE_SETUP_USERNAME_PROMPT["en"]
        ),
        reply_markup=cancel_menu(language),
    )


@router.message(ProfileSetup.waiting_for_username, F.text)
async def receive_profile_setup_username(
    message: Message,
    state: FSMContext,
    settings: Settings,
    session_factory: sessionmaker[Session],
) -> None:
    if message.from_user is None or message.text is None:
        return
    language = user_language(session_factory, message.from_user.id)
    username = message.text.strip().lstrip("@")

    data = await state.get_data()
    pending = data.get("pending", {})
    pending["username"] = username

    await state.set_state(ProfileSetup.managing_account)
    await state.update_data(pending=pending)

    msgs_prof = PROFILE_SETUP_MESSAGES.get(language, PROFILE_SETUP_MESSAGES["en"])
    status = await message.answer(msgs_prof["fetching"])
    await _render_profile_setup_current_account(status, state, settings, language)


@router.callback_query(ProfileSetup.managing_account, F.data == "prof_setup:edit_about")
async def prompt_profile_setup_about(
    callback: CallbackQuery,
    state: FSMContext,
    session_factory: sessionmaker[Session],
) -> None:
    if not isinstance(callback.message, Message):
        return
    language = user_language(session_factory, callback.from_user.id)
    await state.set_state(ProfileSetup.waiting_for_about)
    await callback.answer()
    await callback.message.edit_text(
        PROFILE_SETUP_ABOUT_PROMPT.get(language, PROFILE_SETUP_ABOUT_PROMPT["en"]),
        reply_markup=cancel_menu(language),
    )


@router.message(ProfileSetup.waiting_for_about, F.text)
async def receive_profile_setup_about(
    message: Message,
    state: FSMContext,
    settings: Settings,
    session_factory: sessionmaker[Session],
) -> None:
    if message.from_user is None or message.text is None:
        return
    language = user_language(session_factory, message.from_user.id)
    about = message.text.strip()

    data = await state.get_data()
    pending = data.get("pending", {})
    pending["about"] = about

    await state.set_state(ProfileSetup.managing_account)
    await state.update_data(pending=pending)

    msgs_prof = PROFILE_SETUP_MESSAGES.get(language, PROFILE_SETUP_MESSAGES["en"])
    status = await message.answer(msgs_prof["fetching"])
    await _render_profile_setup_current_account(status, state, settings, language)


@router.callback_query(ProfileSetup.managing_account, F.data == "prof_setup:set_photo")
async def prompt_profile_setup_photo(
    callback: CallbackQuery,
    state: FSMContext,
    session_factory: sessionmaker[Session],
) -> None:
    if not isinstance(callback.message, Message):
        return
    language = user_language(session_factory, callback.from_user.id)
    await state.set_state(ProfileSetup.waiting_for_photo)
    await callback.answer()
    await callback.message.edit_text(
        PROFILE_SETUP_PHOTO_PROMPT.get(language, PROFILE_SETUP_PHOTO_PROMPT["en"]),
        reply_markup=cancel_menu(language),
    )


@router.message(ProfileSetup.waiting_for_photo, F.photo | F.document)
async def receive_profile_setup_photo(
    message: Message,
    bot: Bot,
    state: FSMContext,
    settings: Settings,
    session_factory: sessionmaker[Session],
) -> None:
    if message.from_user is None:
        return
    language = user_language(session_factory, message.from_user.id)
    data = await state.get_data()
    temp_dir_str = data.get("temp_dir")
    if not temp_dir_str:
        await state.clear()
        await message.answer("❌ Session expired.", reply_markup=main_menu(language))
        return

    photo_path = Path(temp_dir_str) / f"photo_{uuid4().hex[:6]}.jpg"
    if message.photo:
        file_id = message.photo[-1].file_id
        await bot.download(file_id, destination=photo_path)
    elif message.document:
        await bot.download(message.document.file_id, destination=photo_path)

    pending = data.get("pending", {})
    pending["photo_path"] = str(photo_path)

    await state.set_state(ProfileSetup.managing_account)
    await state.update_data(pending=pending)

    msgs_prof = PROFILE_SETUP_MESSAGES.get(language, PROFILE_SETUP_MESSAGES["en"])
    status = await message.answer(msgs_prof["fetching"])
    await _render_profile_setup_current_account(status, state, settings, language)


@router.callback_query(ProfileSetup.managing_account, F.data == "prof_setup:apply")
async def action_profile_setup_apply(
    callback: CallbackQuery,
    state: FSMContext,
    settings: Settings,
    session_factory: sessionmaker[Session],
) -> None:
    if not isinstance(callback.message, Message):
        return
    language = user_language(session_factory, callback.from_user.id)
    msgs_prof = PROFILE_SETUP_MESSAGES.get(language, PROFILE_SETUP_MESSAGES["en"])
    await callback.answer()
    status_msg = await callback.message.edit_text(msgs_prof["applying"])

    data = await state.get_data()
    session_files_str = data.get("session_files", [])
    current_index = data.get("current_index", 0)
    modified_count = data.get("modified_count", 0)
    failed_count = data.get("failed_count", 0)
    pending = data.get("pending", {})

    if current_index < len(session_files_str):
        cur_file = Path(session_files_str[current_index])
        photo_path = Path(pending["photo_path"]) if pending.get("photo_path") else None
        ok = await update_account_profile(
            cur_file,
            settings.api_credential_list,
            first_name=pending.get("first_name"),
            last_name=pending.get("last_name"),
            username=pending.get("username"),
            about=pending.get("about"),
            photo_path=photo_path,
        )
        if ok:
            modified_count += 1
        else:
            failed_count += 1

    await state.update_data(
        current_index=current_index + 1,
        modified_count=modified_count,
        failed_count=failed_count,
        pending={},
    )

    if isinstance(status_msg, Message):
        await _render_profile_setup_current_account(
            status_msg, state, settings, language
        )


@router.callback_query(ProfileSetup.managing_account, F.data == "prof_setup:skip")
async def action_profile_setup_skip(
    callback: CallbackQuery,
    state: FSMContext,
    settings: Settings,
    session_factory: sessionmaker[Session],
) -> None:
    if not isinstance(callback.message, Message):
        return
    language = user_language(session_factory, callback.from_user.id)
    await callback.answer()

    data = await state.get_data()
    current_index = data.get("current_index", 0)
    skipped_count = data.get("skipped_count", 0)

    await state.update_data(
        current_index=current_index + 1,
        skipped_count=skipped_count + 1,
        pending={},
    )

    await _render_profile_setup_current_account(
        callback.message, state, settings, language
    )


@router.callback_query(F.data == "prof_setup:noop")
async def profile_setup_noop(callback: CallbackQuery) -> None:
    await callback.answer()


@router.callback_query(F.data == "tool:account_age")
async def request_account_age(
    callback: CallbackQuery,
    state: FSMContext,
    session_factory: sessionmaker[Session],
) -> None:
    language = user_language(session_factory, callback.from_user.id)
    await state.set_state(AccountAge.waiting_for_file)
    await callback.answer()
    if isinstance(callback.message, Message):
        prompt = ENTER_ACCOUNT_AGE_PROMPT.get(language, ENTER_ACCOUNT_AGE_PROMPT["en"])
        await callback.message.edit_text(prompt, reply_markup=cancel_menu(language))


@router.message(AccountAge.waiting_for_file, F.document)
async def receive_account_age_file(
    message: Message,
    bot: Bot,
    state: FSMContext,
    settings: Settings,
    session_factory: sessionmaker[Session],
) -> None:
    if message.from_user is None or message.document is None:
        return
    language = user_language(session_factory, message.from_user.id)
    msgs_age = ACCOUNT_AGE_MESSAGES.get(language, ACCOUNT_AGE_MESSAGES["en"])
    path: Path | None = None
    try:
        path, name = await download_document(message, bot, settings, language)
        status = await message.answer(msgs_age["fetching"])
        if not isinstance(status, Message):
            path.unlink(missing_ok=True)
            await state.clear()
            return

        user_proxy = resolve_user_proxy(session_factory, message.from_user.id)
        res = await process_account_age_check(
            path,
            settings.api_credential_list,
            original_name=name,
            proxy=user_proxy,
        )
        if res.total == 0 or res.checked == 0 or not res.accounts:
            path.unlink(missing_ok=True)
            await state.clear()
            await status.edit_text(
                msgs_age["no_sessions"], reply_markup=main_menu(language)
            )
            return

        if len(res.accounts) > 1:
            await state.set_state(AccountAge.viewing_results)
            await state.update_data(
                accounts=[
                    {
                        "session_name": a.session_name,
                        "user_id": a.user_id,
                        "phone": a.phone,
                        "username": a.username,
                        "first_name": a.first_name,
                        "last_name": a.last_name,
                        "is_premium": a.is_premium,
                        "dc_id": a.dc_id,
                        "creation_estimate": a.creation_estimate,
                        "exact_creation_date": a.exact_creation_date,
                        "is_scam": a.is_scam,
                        "is_fake": a.is_fake,
                        "is_verified": a.is_verified,
                    }
                    for a in res.accounts
                ],
                res_total=res.total,
                res_checked=res.checked,
                res_failed=res.failed,
                page=0,
            )
        else:
            await state.clear()

        report = format_account_age_report(res, msgs_age, page=0)
        await status.edit_text(
            report,
            reply_markup=account_age_result_menu(
                res.total,
                res.checked,
                res.failed,
                language,
                page=0,
                total_pages=len(res.accounts),
            ),
        )
    except Exception:
        LOGGER.exception("Account age check failed for user %s", message.from_user.id)
        await message.answer(msgs_age["no_sessions"], reply_markup=main_menu(language))
        await state.clear()
    finally:
        if path is not None:
            path.unlink(missing_ok=True)


@router.callback_query(F.data == "acc_age:noop")
async def account_age_noop(callback: CallbackQuery) -> None:
    await callback.answer()


@router.callback_query(F.data.startswith("acc_age_page:"))
async def account_age_page_navigate(
    callback: CallbackQuery,
    state: FSMContext,
    session_factory: sessionmaker[Session],
) -> None:
    if callback.data is None or not isinstance(callback.message, Message):
        return
    page = int(callback.data.split(":", 1)[1])
    data = await state.get_data()
    raw_accounts = data.get("accounts", [])
    if not raw_accounts:
        await callback.answer()
        return

    accounts = tuple(AccountAgeInfo(**item) for item in raw_accounts)
    res = AccountAgeResult(
        total=data.get("res_total", len(accounts)),
        checked=data.get("res_checked", len(accounts)),
        failed=data.get("res_failed", 0),
        accounts=accounts,
    )

    total_pages = len(accounts)
    page = max(0, min(page, total_pages - 1))
    await state.update_data(page=page)
    await callback.answer()

    language = user_language(session_factory, callback.from_user.id)
    msgs_age = ACCOUNT_AGE_MESSAGES.get(language, ACCOUNT_AGE_MESSAGES["en"])

    report = format_account_age_report(res, msgs_age, page=page)
    await callback.message.edit_text(
        report,
        reply_markup=account_age_result_menu(
            res.total,
            res.checked,
            res.failed,
            language,
            page=page,
            total_pages=total_pages,
        ),
    )


@router.callback_query(F.data == "tool:clear_contact")
async def request_clear_contacts(
    callback: CallbackQuery,
    state: FSMContext,
    session_factory: sessionmaker[Session],
) -> None:
    language = user_language(session_factory, callback.from_user.id)
    await state.set_state(ClearContacts.waiting_for_file)
    await callback.answer()
    if isinstance(callback.message, Message):
        await callback.message.edit_text(
            ENTER_CLEAR_CONTACTS_PROMPT.get(
                language, ENTER_CLEAR_CONTACTS_PROMPT["en"]
            ),
            reply_markup=cancel_menu(language),
        )


@router.message(ClearContacts.waiting_for_file, F.document)
async def receive_clear_contacts_file(
    message: Message,
    bot: Bot,
    state: FSMContext,
    settings: Settings,
    session_factory: sessionmaker[Session],
) -> None:
    if message.from_user is None or message.document is None:
        return
    language = user_language(session_factory, message.from_user.id)
    msgs_clear = CLEAR_CONTACTS_MESSAGES.get(language, CLEAR_CONTACTS_MESSAGES["en"])
    path: Path | None = None
    try:
        path, name = await download_document(message, bot, settings, language)
        sessions = await inspect_mergeable_sessions(path)
        if not sessions:
            path.unlink(missing_ok=True)
            await state.clear()
            await message.answer(
                msgs_clear["no_sessions"], reply_markup=main_menu(language)
            )
            return

        status = await message.answer(msgs_clear["processing"])
        out_res: Path | None = None
        try:
            user_proxy = resolve_user_proxy(session_factory, message.from_user.id)
            res_clr = await process_clear_contacts(
                path,
                output_dir=settings.storage_dir / "outbox",
                credentials=settings.api_credential_list,
                original_name=name,
                proxy=user_proxy,
            )
            out_res = res_clr.output_path
            if res_clr.cleared == 0:
                report = msgs_clear["failed_report"].format(failed=res_clr.failed)
            else:
                report = msgs_clear["done"].format(
                    success=res_clr.cleared, failed=res_clr.failed
                )
            await status.edit_text(
                report,
                reply_markup=clear_contacts_result_menu(
                    res_clr.total, res_clr.cleared, res_clr.failed, language
                ),
            )
            if out_res and out_res.exists():
                await message.answer_document(
                    FSInputFile(out_res, filename=out_res.name)
                )
        except Exception:
            LOGGER.exception("Clear contacts error for user %s", message.from_user.id)
            await status.edit_text(
                msgs_clear["request_failed"], reply_markup=main_menu(language)
            )
        finally:
            if out_res and out_res.exists():
                out_res.unlink(missing_ok=True)
    except Exception as exc:  # noqa: BLE001
        archive_errors = ARCHIVE_ERRORS.get(language, ARCHIVE_ERRORS["en"])
        error = archive_errors.get(str(exc), str(exc))
        await message.answer(
            f"❌ {html.quote(error)}", reply_markup=cancel_menu(language)
        )
    finally:
        if path is not None:
            path.unlink(missing_ok=True)
        await state.clear()


@router.callback_query(F.data == "clear_contact:noop")
async def clear_contacts_noop(callback: CallbackQuery) -> None:
    await callback.answer()


@router.callback_query(F.data == "tool:kill_sessions")
async def request_kill_sessions(
    callback: CallbackQuery,
    state: FSMContext,
    session_factory: sessionmaker[Session],
) -> None:
    language = user_language(session_factory, callback.from_user.id)
    await state.set_state(KillSessions.waiting_for_file)
    await callback.answer()
    if isinstance(callback.message, Message):
        await callback.message.edit_text(
            ENTER_KILL_SESSIONS_PROMPT.get(language, ENTER_KILL_SESSIONS_PROMPT["en"]),
            reply_markup=cancel_menu(language),
        )


@router.message(KillSessions.waiting_for_file, F.document)
async def receive_kill_sessions_file(
    message: Message,
    bot: Bot,
    state: FSMContext,
    settings: Settings,
    session_factory: sessionmaker[Session],
) -> None:
    if message.from_user is None or message.document is None:
        return
    language = user_language(session_factory, message.from_user.id)
    msgs = KILL_SESSIONS_MESSAGES.get(language, KILL_SESSIONS_MESSAGES["en"])
    path: Path | None = None
    saved_file: Path | None = None
    try:
        path, name = await download_document(message, bot, settings, language)
        sessions = await inspect_mergeable_sessions(path)
        if not sessions:
            path.unlink(missing_ok=True)
            await state.clear()
            await message.answer(msgs["no_sessions"], reply_markup=main_menu(language))
            return

        temp_storage = settings.storage_dir / "temp" / f"kill_{uuid4().hex}"
        temp_storage.parent.mkdir(parents=True, exist_ok=True)
        saved_file = temp_storage.with_suffix(Path(name).suffix)
        shutil.copy2(path, saved_file)

        await state.set_state(KillSessions.confirming)
        await state.update_data(
            file_path=str(saved_file),
            original_name=name,
        )

        confirm_text = KILL_SESSIONS_CONFIRM_PROMPT.get(
            language, KILL_SESSIONS_CONFIRM_PROMPT["en"]
        )
        await message.answer(
            confirm_text,
            reply_markup=kill_sessions_confirm_menu(language),
        )
    except Exception as exc:  # noqa: BLE001
        if saved_file is not None:
            saved_file.unlink(missing_ok=True)
        archive_errors = ARCHIVE_ERRORS.get(language, ARCHIVE_ERRORS["en"])
        error = archive_errors.get(str(exc), str(exc))
        await message.answer(
            f"❌ {html.quote(error)}", reply_markup=cancel_menu(language)
        )
        await state.clear()
    finally:
        if path is not None:
            path.unlink(missing_ok=True)


@router.callback_query(
    StateFilter(KillSessions.confirming), F.data == "kill_sess:confirm"
)
async def confirm_kill_sessions(
    callback: CallbackQuery,
    state: FSMContext,
    settings: Settings,
    session_factory: sessionmaker[Session],
) -> None:
    if callback.from_user is None or not isinstance(callback.message, Message):
        return
    language = user_language(session_factory, callback.from_user.id)
    msgs = KILL_SESSIONS_MESSAGES.get(language, KILL_SESSIONS_MESSAGES["en"])
    await callback.answer()

    data = await state.get_data()
    file_path_str = data.get("file_path")
    original_name = data.get("original_name")

    if not file_path_str:
        await callback.message.edit_text(
            msgs["no_sessions"], reply_markup=main_menu(language)
        )
        await state.clear()
        return

    input_path = Path(file_path_str)
    await callback.message.edit_text(msgs["processing"])

    try:
        user_proxy = resolve_user_proxy(session_factory, callback.from_user.id)
        res = await process_kill_sessions(
            input_path,
            credentials=settings.api_credential_list,
            original_name=original_name,
            proxy=user_proxy,
        )
        report = msgs["done"].format(
            killed=res.killed,
            fresh_forbidden=res.fresh_forbidden,
            failed=res.failed,
        )
        await callback.message.edit_text(
            report,
            reply_markup=kill_sessions_result_menu(
                res.total, res.killed, res.fresh_forbidden, res.failed, language
            ),
        )
    except Exception:
        LOGGER.exception("Kill sessions error for user %s", callback.from_user.id)
        await callback.message.edit_text(
            msgs["request_failed"], reply_markup=main_menu(language)
        )
    finally:
        input_path.unlink(missing_ok=True)
        await state.clear()


@router.callback_query(F.data == "kill_sess:noop")
async def kill_sessions_noop(callback: CallbackQuery) -> None:
    await callback.answer()


# ── Fresh Session handlers ────────────────────────────────────────────────────


@router.callback_query(F.data == "tool:fresh_session")
async def request_fresh_session(
    callback: CallbackQuery,
    state: FSMContext,
    session_factory: sessionmaker[Session],
) -> None:
    language = user_language(session_factory, callback.from_user.id)
    await state.set_state(FreshSession.waiting_for_file)
    await callback.answer()
    if isinstance(callback.message, Message):
        await callback.message.edit_text(
            ENTER_FRESH_SESSION_PROMPT.get(language, ENTER_FRESH_SESSION_PROMPT["en"]),
            reply_markup=cancel_menu(language),
        )


@router.message(FreshSession.waiting_for_file, F.document)
async def receive_fresh_session_file(
    message: Message,
    bot: Bot,
    state: FSMContext,
    settings: Settings,
    session_factory: sessionmaker[Session],
) -> None:
    if message.from_user is None or message.document is None:
        return
    language = user_language(session_factory, message.from_user.id)
    msgs = FRESH_SESSION_MESSAGES.get(language, FRESH_SESSION_MESSAGES["en"])
    path: Path | None = None
    saved_file: Path | None = None
    try:
        path, name = await download_document(message, bot, settings, language)
        sessions = await inspect_mergeable_sessions(path)
        if not sessions:
            path.unlink(missing_ok=True)
            await state.clear()
            await message.answer(msgs["no_sessions"], reply_markup=main_menu(language))
            return

        temp_storage = settings.storage_dir / "temp" / f"fresh_{uuid4().hex}"
        temp_storage.parent.mkdir(parents=True, exist_ok=True)
        saved_file = temp_storage.with_suffix(Path(name).suffix)
        shutil.copy2(path, saved_file)

        await state.update_data(file_path=str(saved_file), original_name=name)
        await state.set_state(FreshSession.waiting_for_2fa)

        await message.answer(
            EmojiRegistry.enrich(
                FRESH_SESSION_2FA_PROMPT.get(language, FRESH_SESSION_2FA_PROMPT["en"])
            ),
            reply_markup=fresh_session_2fa_menu(language),
        )
    except Exception as exc:  # noqa: BLE001
        if saved_file is not None:
            saved_file.unlink(missing_ok=True)
        archive_errors = ARCHIVE_ERRORS.get(language, ARCHIVE_ERRORS["en"])
        error = archive_errors.get(str(exc), str(exc))
        await message.answer(
            f"❌ {html.quote(error)}", reply_markup=cancel_menu(language)
        )
        await state.clear()
    finally:
        if path is not None:
            path.unlink(missing_ok=True)


@router.message(FreshSession.waiting_for_2fa, F.text)
async def receive_fresh_session_2fa(
    message: Message,
    state: FSMContext,
    session_factory: sessionmaker[Session],
) -> None:
    if message.from_user is None or not message.text:
        return
    language = user_language(session_factory, message.from_user.id)
    password = message.text.strip()
    with suppress(Exception):
        await message.delete()
    await state.update_data(password_2fa=password)
    await state.set_state(FreshSession.confirming)
    await message.answer(
        EmojiRegistry.enrich(
            FRESH_SESSION_CONFIRM_PROMPT.get(language, FRESH_SESSION_CONFIRM_PROMPT["en"])
        ),
        reply_markup=fresh_session_confirm_menu(language),
    )


@router.callback_query(
    StateFilter(FreshSession.waiting_for_2fa), F.data == "fresh_sess:skip_2fa"
)
async def skip_fresh_session_2fa(
    callback: CallbackQuery,
    state: FSMContext,
    session_factory: sessionmaker[Session],
) -> None:
    if callback.from_user is None or not isinstance(callback.message, Message):
        return
    language = user_language(session_factory, callback.from_user.id)
    await callback.answer()
    await state.update_data(password_2fa=None)
    await state.set_state(FreshSession.confirming)
    await callback.message.edit_text(
        EmojiRegistry.enrich(
            FRESH_SESSION_CONFIRM_PROMPT.get(language, FRESH_SESSION_CONFIRM_PROMPT["en"])
        ),
        reply_markup=fresh_session_confirm_menu(language),
    )


@router.callback_query(
    StateFilter(FreshSession.confirming), F.data == "fresh_sess:confirm"
)
async def confirm_fresh_session(
    callback: CallbackQuery,
    state: FSMContext,
    bot: Bot,
    settings: Settings,
    session_factory: sessionmaker[Session],
) -> None:
    if callback.from_user is None or not isinstance(callback.message, Message):
        return
    language = user_language(session_factory, callback.from_user.id)
    msgs = FRESH_SESSION_MESSAGES.get(language, FRESH_SESSION_MESSAGES["en"])
    await callback.answer()

    data = await state.get_data()
    file_path_str = data.get("file_path")
    original_name = data.get("original_name")
    password_2fa = data.get("password_2fa")

    if not file_path_str:
        await callback.message.edit_text(
            msgs["no_sessions"], reply_markup=main_menu(language)
        )
        await state.clear()
        return

    input_path = Path(file_path_str)
    await callback.message.edit_text(msgs["processing"])

    try:
        res = await process_fresh_sessions(
            input_path,
            credentials=settings.api_credential_list,
            original_name=original_name,
            password_2fa=password_2fa or None,
        )

        # Send new sessions ZIP
        if res.new_sessions_zip and res.new_sessions_zip.exists():
            caption = msgs["new_zip_caption"].format(succeeded=res.succeeded)
            await bot.send_document(
                chat_id=callback.from_user.id,
                document=FSInputFile(
                    res.new_sessions_zip, filename="fresh_sessions.zip"
                ),
                caption=caption,
            )
            res.new_sessions_zip.unlink(missing_ok=True)

        # Send failed ZIP
        if res.failed_zip and res.failed_zip.exists():
            caption = msgs["fail_zip_caption"].format(failed=res.failed)
            await bot.send_document(
                chat_id=callback.from_user.id,
                document=FSInputFile(res.failed_zip, filename="failed_sessions.zip"),
                caption=caption,
            )
            res.failed_zip.unlink(missing_ok=True)

        # Build per-session detail lines: Old → New (or error reason)
        detail_lines: list[str] = []
        for d in res.details:
            old_name = html.quote(d.session_name)
            if d.status == "ok":
                new_name = html.quote(f"{d.phone}.session") if d.phone else old_name
                detail_lines.append(
                    f"✅ <code>{old_name}</code> → <code>{new_name}</code>"
                )
            else:
                reason = html.quote(d.message[:60])
                detail_lines.append(f"❌ <code>{old_name}</code> — {reason}")
        details_str = "\n".join(detail_lines)

        summary_key = "done" if res.new_sessions_zip else "no_new"
        report = msgs[summary_key].format(
            succeeded=res.succeeded, failed=res.failed, details=details_str
        )
        await callback.message.edit_text(
            report,
            reply_markup=fresh_session_result_menu(
                res.total, res.succeeded, res.failed, language
            ),
        )
    except Exception:
        LOGGER.exception("Fresh session error for user %s", callback.from_user.id)
        await callback.message.edit_text(
            msgs["request_failed"], reply_markup=main_menu(language)
        )
    finally:
        input_path.unlink(missing_ok=True)
        await state.clear()


@router.callback_query(F.data == "fresh_sess:noop")
async def fresh_session_noop(callback: CallbackQuery) -> None:
    await callback.answer()


# ─── List Checker Flow ─────────────────────────────────────────────────────────


@router.callback_query(F.data == "tool:list_checker")
async def request_list_checker(
    callback: CallbackQuery,
    state: FSMContext,
    session_factory: sessionmaker[Session],
) -> None:
    await callback.answer()
    if not isinstance(callback.message, Message):
        return
    with session_factory() as db_sess:
        language = get_user_language(db_sess, callback.from_user.id)
    msgs = LIST_CHECKER_MESSAGES.get(language, LIST_CHECKER_MESSAGES["en"])
    await state.set_state(ListChecker.waiting_for_file1)
    await callback.message.edit_text(
        msgs["file1_prompt"],
        reply_markup=list_checker_cancel_menu(language),
    )


@router.message(StateFilter(ListChecker.waiting_for_file1), F.document)
async def receive_list_checker_file1(
    message: Message,
    state: FSMContext,
    bot: Bot,
    session_factory: sessionmaker[Session],
) -> None:
    if not message.document or not message.from_user:
        return
    with session_factory() as db_sess:
        language = get_user_language(db_sess, message.from_user.id)
    msgs = LIST_CHECKER_MESSAGES.get(language, LIST_CHECKER_MESSAGES["en"])

    filename = Path(message.document.file_name or "file1.zip").name
    if not filename.lower().endswith(".zip"):
        await message.reply(
            msgs["invalid_format"], reply_markup=list_checker_cancel_menu(language)
        )
        return

    temp_dir = Path(tempfile.mkdtemp(prefix="ftgc_list_checker_"))
    file1_path = temp_dir / filename
    try:
        await bot.download(message.document, destination=file1_path)
    except Exception:
        LOGGER.exception(
            "List checker file1 download failed for user %s", message.from_user.id
        )
        shutil.rmtree(temp_dir, ignore_errors=True)
        await state.clear()
        await message.reply(
            msgs["download_failed"], reply_markup=main_menu(language)
        )
        return

    await state.update_data(
        temp_dir=str(temp_dir),
        file1_path=str(file1_path),
        file1_name=filename,
    )
    await state.set_state(ListChecker.waiting_for_file2)
    prompt = msgs["file2_prompt"].format(name=html.quote(filename))
    await message.reply(prompt, reply_markup=list_checker_cancel_menu(language))


@router.message(StateFilter(ListChecker.waiting_for_file2), F.document)
async def receive_list_checker_file2(
    message: Message,
    state: FSMContext,
    bot: Bot,
    session_factory: sessionmaker[Session],
) -> None:
    if not message.document or not message.from_user:
        return
    with session_factory() as db_sess:
        language = get_user_language(db_sess, message.from_user.id)
    msgs = LIST_CHECKER_MESSAGES.get(language, LIST_CHECKER_MESSAGES["en"])

    filename = Path(message.document.file_name or "file2.zip").name
    if not filename.lower().endswith(".zip"):
        await message.reply(
            msgs["invalid_format"], reply_markup=list_checker_cancel_menu(language)
        )
        return

    data = await state.get_data()
    temp_dir_str = data.get("temp_dir")
    file1_path_str = data.get("file1_path")
    if not temp_dir_str or not file1_path_str:
        await state.clear()
        await message.reply(
            msgs["file1_prompt"], reply_markup=list_checker_cancel_menu(language)
        )
        return

    temp_dir = Path(temp_dir_str)
    file1_path = Path(file1_path_str)
    file2_path = temp_dir / filename

    proc_msg = await message.reply(msgs["processing"])

    try:
        await bot.download(message.document, destination=file2_path)
    except Exception:
        LOGGER.exception(
            "List checker file2 download failed for user %s", message.from_user.id
        )
        await proc_msg.edit_text(
            msgs["download_failed"], reply_markup=main_menu(language)
        )
        return
    try:
        res = await asyncio.to_thread(compare_archive_files, file1_path, file2_path)

        if res.total == 0:
            await proc_msg.edit_text(msgs["no_match"], reply_markup=main_menu(language))
        else:
            if res.output_bytes:
                input_file = BufferedInputFile(
                    res.output_bytes, filename="matched_files.zip"
                )
                caption = msgs["result_caption"].format(total=res.total)
                await message.reply_document(document=input_file, caption=caption)

            report = msgs["done"].format(
                tdata=res.tdata_count,
                session=res.session_count,
                json=res.json_count,
                total=res.total,
            )
            await proc_msg.edit_text(
                report,
                reply_markup=list_checker_result_menu(
                    res.tdata_count,
                    res.session_count,
                    res.json_count,
                    res.total,
                    language,
                ),
            )
    except Exception as e:  # noqa: BLE001
        LOGGER.warning("List checker error: %s", e)
        await proc_msg.edit_text(
            msgs["invalid_format"], reply_markup=main_menu(language)
        )
    finally:
        if temp_dir_str:
            import shutil

            shutil.rmtree(temp_dir_str, ignore_errors=True)
        await state.clear()


# ── Privacy Settings Handlers ────────────────────────────────────────────────


@router.callback_query(F.data == "tool:privacy_settings")
async def start_privacy_settings(
    callback: CallbackQuery,
    state: FSMContext,
    session_factory: sessionmaker[Session],
) -> None:
    if not isinstance(callback.message, Message) or not callback.from_user:
        return
    with session_factory() as db_sess:
        language = get_user_language(db_sess, callback.from_user.id)
    msgs = PRIVACY_SETTINGS_MESSAGES.get(language, PRIVACY_SETTINGS_MESSAGES["en"])
    await state.set_state(PrivacySettings.waiting_for_file)
    await callback.message.edit_text(
        EmojiRegistry.enrich(msgs["prompt_file"]),
        reply_markup=cancel_menu(language),
    )


@router.message(StateFilter(PrivacySettings.waiting_for_file), F.document)
async def receive_privacy_settings_file(
    message: Message,
    state: FSMContext,
    bot: Bot,
    session_factory: sessionmaker[Session],
) -> None:
    if not message.document or not message.from_user:
        return
    with session_factory() as db_sess:
        language = get_user_language(db_sess, message.from_user.id)
    msgs = PRIVACY_SETTINGS_MESSAGES.get(language, PRIVACY_SETTINGS_MESSAGES["en"])

    filename = message.document.file_name or "session.zip"
    ext = Path(filename).suffix.lower()
    if ext not in (".session", ".zip"):
        await message.reply(
            msgs["invalid_file"],
            reply_markup=cancel_menu(language),
        )
        return

    temp_dir = Path(tempfile.mkdtemp(prefix="ftgc_privacy_"))
    saved_file = temp_dir / filename
    await bot.download(message.document, destination=saved_file)

    await state.update_data(
        temp_dir=str(temp_dir),
        file_path=str(saved_file),
        filename=filename,
    )
    await state.set_state(PrivacySettings.selecting_mode)
    await message.reply(
        EmojiRegistry.enrich(msgs["prompt_mode"]),
        reply_markup=privacy_mode_menu(language),
    )


@router.callback_query(
    StateFilter(PrivacySettings.waiting_for_2fa), F.data == "privacy:skip_2fa"
)
async def privacy_skip_2fa_callback(
    callback: CallbackQuery,
    state: FSMContext,
    session_factory: sessionmaker[Session],
) -> None:
    if not isinstance(callback.message, Message) or not callback.from_user:
        return
    with session_factory() as db_sess:
        language = get_user_language(db_sess, callback.from_user.id)
    msgs = PRIVACY_SETTINGS_MESSAGES.get(language, PRIVACY_SETTINGS_MESSAGES["en"])
    await state.set_state(PrivacySettings.selecting_mode)
    await callback.message.edit_text(
        EmojiRegistry.enrich(msgs["prompt_mode"]), reply_markup=privacy_mode_menu(language)
    )


@router.callback_query(F.data == "privacy:skip_2fa")
async def skip_privacy_settings_2fa(
    callback: CallbackQuery,
    state: FSMContext,
    session_factory: sessionmaker[Session],
) -> None:
    if not isinstance(callback.message, Message) or not callback.from_user:
        return
    with session_factory() as db_sess:
        language = get_user_language(db_sess, callback.from_user.id)
    msgs = PRIVACY_SETTINGS_MESSAGES.get(language, PRIVACY_SETTINGS_MESSAGES["en"])

    await state.update_data(password=None)
    await state.set_state(PrivacySettings.selecting_mode)
    await callback.message.edit_text(
        EmojiRegistry.enrich(msgs["prompt_mode"]), reply_markup=privacy_mode_menu(language)
    )


@router.callback_query(F.data.startswith("privacy:mode:"))
async def select_privacy_mode(
    callback: CallbackQuery,
    state: FSMContext,
    session_factory: sessionmaker[Session],
) -> None:
    if (
        not isinstance(callback.message, Message)
        or not callback.from_user
        or not callback.data
    ):
        return
    with session_factory() as db_sess:
        language = get_user_language(db_sess, callback.from_user.id)
    msgs = PRIVACY_SETTINGS_MESSAGES.get(language, PRIVACY_SETTINGS_MESSAGES["en"])

    mode = callback.data.split(":")[-1]
    if mode == "preset":
        await state.set_state(PrivacySettings.selecting_preset)
        await callback.message.edit_text(
            EmojiRegistry.enrich(msgs["prompt_preset"]),
            reply_markup=privacy_presets_menu(language),
        )
    elif mode == "custom":
        data = await state.get_data()
        current_rules = data.get("custom_rules") or {
            "last_seen": "nobody",
            "phone_number": "nobody",
            "profile_photo": "contacts",
            "forwarded_messages": "nobody",
            "calls": "nobody",
            "p2p_calls": "nobody",
            "group_invites": "contacts",
            "voice_messages": "nobody",
        }
        await state.update_data(custom_rules=current_rules)
        await state.set_state(PrivacySettings.selecting_rule_key)
        await callback.message.edit_text(
            EmojiRegistry.enrich(msgs["prompt_rule_key"]),
            reply_markup=privacy_custom_menu(language, current_rules),
        )


@router.callback_query(F.data == "privacy:back_mode")
async def privacy_back_mode(
    callback: CallbackQuery,
    state: FSMContext,
    session_factory: sessionmaker[Session],
) -> None:
    if not isinstance(callback.message, Message) or not callback.from_user:
        return
    with session_factory() as db_sess:
        language = get_user_language(db_sess, callback.from_user.id)
    msgs = PRIVACY_SETTINGS_MESSAGES.get(language, PRIVACY_SETTINGS_MESSAGES["en"])
    await state.set_state(PrivacySettings.selecting_mode)
    await callback.message.edit_text(
        EmojiRegistry.enrich(msgs["prompt_mode"]), reply_markup=privacy_mode_menu(language)
    )


@router.callback_query(F.data == "privacy:back_custom")
async def privacy_back_custom(
    callback: CallbackQuery,
    state: FSMContext,
    session_factory: sessionmaker[Session],
) -> None:
    if not isinstance(callback.message, Message) or not callback.from_user:
        return
    with session_factory() as db_sess:
        language = get_user_language(db_sess, callback.from_user.id)
    msgs = PRIVACY_SETTINGS_MESSAGES.get(language, PRIVACY_SETTINGS_MESSAGES["en"])
    data = await state.get_data()
    current_rules = data.get("custom_rules") or {}
    await state.set_state(PrivacySettings.selecting_rule_key)
    await callback.message.edit_text(
        EmojiRegistry.enrich(msgs["prompt_rule_key"]),
        reply_markup=privacy_custom_menu(language, current_rules),
    )


@router.callback_query(F.data.startswith("privacy:preset:"))
async def apply_privacy_preset_handler(
    callback: CallbackQuery,
    state: FSMContext,
    session_factory: sessionmaker[Session],
) -> None:
    if (
        not isinstance(callback.message, Message)
        or not callback.from_user
        or not callback.data
    ):
        return
    with session_factory() as db_sess:
        language = get_user_language(db_sess, callback.from_user.id)
    msgs = PRIVACY_SETTINGS_MESSAGES.get(language, PRIVACY_SETTINGS_MESSAGES["en"])

    preset_name = callback.data.split(":")[-1]
    data = await state.get_data()
    file_path_str = data.get("file_path")
    temp_dir_str = data.get("temp_dir")
    password = data.get("password")

    if not file_path_str:
        await state.clear()
        await callback.message.edit_text(
            EmojiRegistry.enrich(msgs["invalid_file"]), reply_markup=main_menu(language)
        )
        return

    proc_msg = await callback.message.edit_text(EmojiRegistry.enrich(msgs["processing"]))
    if not isinstance(proc_msg, Message):
        return

    file_path = Path(file_path_str)
    try:
        user_proxy = resolve_user_proxy(session_factory, callback.from_user.id)
        res = await process_privacy_settings(
            input_path=file_path,
            password=password,
            preset_name=preset_name,
            proxy=user_proxy,
        )

        preset_label = msgs["presets"].get(preset_name, preset_name)
        details_text = ""
        failed_sessions = [d.session_name for d in res.details if d.status != "ok"]
        if failed_sessions:
            details_text = (
                f"\n{EmojiRegistry.divider_line()}\n\n"
                "<b>Failed Sessions:</b>\n• "
                + "\n• ".join(failed_sessions[:10])
            )

        report = EmojiRegistry.enrich(
            msgs["done"].format(
                total=res.total,
                succeeded=res.succeeded,
                failed=res.failed,
                preset=preset_label,
                details=details_text,
            )
        )

        await proc_msg.edit_text(
            report,
            reply_markup=privacy_result_menu(
                res.total, res.succeeded, res.failed, language
            ),
        )
    except Exception:
        LOGGER.exception(
            "Privacy settings processing error for user %s", callback.from_user.id
        )
        await proc_msg.edit_text(
            EmojiRegistry.enrich(msgs["invalid_file"]), reply_markup=main_menu(language)
        )
    finally:
        if temp_dir_str:
            import shutil

            shutil.rmtree(temp_dir_str, ignore_errors=True)
        await state.clear()


@router.callback_query(F.data.startswith("privacy:rule:"))
async def select_privacy_rule_key(
    callback: CallbackQuery,
    state: FSMContext,
    session_factory: sessionmaker[Session],
) -> None:
    if (
        not isinstance(callback.message, Message)
        or not callback.from_user
        or not callback.data
    ):
        return
    with session_factory() as db_sess:
        language = get_user_language(db_sess, callback.from_user.id)
    msgs = PRIVACY_SETTINGS_MESSAGES.get(language, PRIVACY_SETTINGS_MESSAGES["en"])

    rule_key = callback.data.split(":")[-1]
    rule_name = msgs["rules"].get(rule_key, rule_key)

    await state.update_data(active_rule_key=rule_key)
    await state.set_state(PrivacySettings.selecting_rule_value)
    prompt = msgs["prompt_rule_value"].format(rule_name=rule_name)
    await callback.message.edit_text(
        EmojiRegistry.enrich(prompt), reply_markup=privacy_value_menu(language, rule_key)
    )


@router.callback_query(F.data.startswith("privacy:val:"))
async def select_privacy_rule_value(
    callback: CallbackQuery,
    state: FSMContext,
    session_factory: sessionmaker[Session],
) -> None:
    if (
        not isinstance(callback.message, Message)
        or not callback.from_user
        or not callback.data
    ):
        return
    with session_factory() as db_sess:
        language = get_user_language(db_sess, callback.from_user.id)
    msgs = PRIVACY_SETTINGS_MESSAGES.get(language, PRIVACY_SETTINGS_MESSAGES["en"])

    parts = callback.data.split(":")
    rule_key = parts[2]
    choice_val = parts[3]

    data = await state.get_data()
    custom_rules = data.get("custom_rules") or {}
    custom_rules[rule_key] = choice_val

    await state.update_data(custom_rules=custom_rules)
    await state.set_state(PrivacySettings.selecting_rule_key)
    await callback.message.edit_text(
        EmojiRegistry.enrich(msgs["prompt_rule_key"]),
        reply_markup=privacy_custom_menu(language, custom_rules),
    )


@router.callback_query(F.data == "privacy:apply_custom")
async def apply_custom_privacy_handler(
    callback: CallbackQuery,
    state: FSMContext,
    session_factory: sessionmaker[Session],
) -> None:
    if not isinstance(callback.message, Message) or not callback.from_user:
        return
    with session_factory() as db_sess:
        language = get_user_language(db_sess, callback.from_user.id)
    msgs = PRIVACY_SETTINGS_MESSAGES.get(language, PRIVACY_SETTINGS_MESSAGES["en"])

    data = await state.get_data()
    file_path_str = data.get("file_path")
    temp_dir_str = data.get("temp_dir")
    password = data.get("password")
    custom_rules = data.get("custom_rules") or {}

    if not file_path_str:
        await state.clear()
        await callback.message.edit_text(
            EmojiRegistry.enrich(msgs["invalid_file"]), reply_markup=main_menu(language)
        )
        return

    proc_msg = await callback.message.edit_text(EmojiRegistry.enrich(msgs["processing"]))
    if not isinstance(proc_msg, Message):
        return

    file_path = Path(file_path_str)
    try:
        user_proxy = resolve_user_proxy(session_factory, callback.from_user.id)
        res = await process_privacy_settings(
            input_path=file_path,
            password=password,
            rules=custom_rules,
            preset_name="custom",
            proxy=user_proxy,
        )

        preset_label = msgs["presets"].get("custom", "Custom Rules")
        details_text = ""
        failed_sessions = [d.session_name for d in res.details if d.status != "ok"]
        if failed_sessions:
            details_text = (
                f"\n{EmojiRegistry.divider_line()}\n\n"
                "<b>Failed Sessions:</b>\n• "
                + "\n• ".join(failed_sessions[:10])
            )

        report = EmojiRegistry.enrich(
            msgs["done"].format(
                total=res.total,
                succeeded=res.succeeded,
                failed=res.failed,
                preset=preset_label,
                details=details_text,
            )
        )

        await proc_msg.edit_text(
            report,
            reply_markup=privacy_result_menu(
                res.total, res.succeeded, res.failed, language
            ),
        )
    except Exception:
        LOGGER.exception(
            "Custom privacy settings processing error for user %s",
            callback.from_user.id,
        )
        await proc_msg.edit_text(
            EmojiRegistry.enrich(msgs["invalid_file"]), reply_markup=main_menu(language)
        )
    finally:
        if temp_dir_str:
            import shutil

            shutil.rmtree(temp_dir_str, ignore_errors=True)
        await state.clear()


@router.callback_query(F.data == "privacy:noop")
async def privacy_noop_handler(callback: CallbackQuery) -> None:
    await callback.answer()


@router.callback_query(F.data == "list_check:noop")
async def list_check_noop(callback: CallbackQuery) -> None:
    await callback.answer()


@router.callback_query(F.data == "tool:channel_join")
async def request_channel_join(
    callback: CallbackQuery,
    state: FSMContext,
    session_factory: sessionmaker[Session],
) -> None:
    language = user_language(session_factory, callback.from_user.id)
    await state.set_state(ChannelJoin.waiting_for_file)
    await callback.answer()
    if isinstance(callback.message, Message):
        await callback.message.edit_text(
            CHANNEL_JOIN_PROMPTS.get(language, CHANNEL_JOIN_PROMPTS["en"]),
            reply_markup=cancel_menu(language),
        )


@router.callback_query(F.data == "tool:leave_channel")
async def request_leave_channel(
    callback: CallbackQuery,
    state: FSMContext,
    session_factory: sessionmaker[Session],
) -> None:
    language = user_language(session_factory, callback.from_user.id)
    await state.set_state(ChannelLeave.waiting_for_file)
    await callback.answer()
    if isinstance(callback.message, Message):
        await callback.message.edit_text(
            CHANNEL_LEAVE_PROMPTS.get(language, CHANNEL_LEAVE_PROMPTS["en"]),
            reply_markup=cancel_menu(language),
        )


@router.message(ChannelJoin.waiting_for_file, F.document)
async def receive_channel_join_file(
    message: Message,
    bot: Bot,
    state: FSMContext,
    settings: Settings,
    session_factory: sessionmaker[Session],
) -> None:
    if message.from_user is None or message.document is None:
        return
    language = user_language(session_factory, message.from_user.id)
    msgs_chan = CHANNEL_MESSAGES.get(language, CHANNEL_MESSAGES["en"])
    path: Path | None = None
    try:
        path, name = await download_document(message, bot, settings, language)
        sessions = await inspect_mergeable_sessions(path)
        if not sessions:
            path.unlink(missing_ok=True)
            await state.clear()
            await message.answer(
                msgs_chan["no_sessions"], reply_markup=main_menu(language)
            )
            return

        await state.update_data(temp_file_path=str(path), original_name=name)
        await state.set_state(ChannelJoin.waiting_for_target)
        fmt = ENTER_CHANNEL_JOIN_TARGET_PROMPT.get(
            language, ENTER_CHANNEL_JOIN_TARGET_PROMPT["en"]
        )
        await message.answer(
            fmt.format(count=len(sessions)), reply_markup=cancel_menu(language)
        )
    except Exception as exc:  # noqa: BLE001
        if path is not None:
            path.unlink(missing_ok=True)
        archive_errors = ARCHIVE_ERRORS.get(language, ARCHIVE_ERRORS["en"])
        error = archive_errors.get(str(exc), str(exc))
        await message.answer(
            f"❌ {html.quote(error)}", reply_markup=cancel_menu(language)
        )


@router.callback_query(F.data == "channel:noop")
async def channel_noop(callback: CallbackQuery) -> None:
    await callback.answer()


@router.message(ChannelJoin.waiting_for_target, F.text)
async def receive_channel_join_target(
    message: Message,
    state: FSMContext,
    settings: Settings,
    session_factory: sessionmaker[Session],
) -> None:
    if message.from_user is None or not message.text:
        return
    language = user_language(session_factory, message.from_user.id)
    msgs_chan = CHANNEL_MESSAGES.get(language, CHANNEL_MESSAGES["en"])
    data = await state.get_data()
    file_str = data.get("temp_file_path")
    if not file_str:
        await state.clear()
        await message.answer(msgs_chan["no_sessions"], reply_markup=main_menu(language))
        return

    file_path = Path(file_str)
    original_name = data.get("original_name")
    target = message.text.strip()
    if not target or target.lower() in ("all", "*") or " " in target:
        await message.answer(
            msgs_chan["invalid_target"], reply_markup=cancel_menu(language)
        )
        return
    status = await message.answer(msgs_chan["processing"])
    out_res: Path | None = None
    try:
        try:
            res_chan = await process_channel_join(
                file_path,
                output_dir=settings.storage_dir / "outbox",
                target=target,
                credentials=settings.api_credential_list,
                original_name=original_name,
            )
            out_res = res_chan.output_path
            if res_chan.success == 0:
                report = msgs_chan["failed_report"].format(failed=res_chan.failed)
            else:
                report = msgs_chan["done"].format(
                    success=res_chan.success, failed=res_chan.failed
                )
            await status.edit_text(
                report,
                reply_markup=channel_result_menu(
                    res_chan.total, res_chan.success, res_chan.failed, language
                ),
            )
            if out_res and out_res.exists():
                await message.answer_document(
                    FSInputFile(out_res, filename=out_res.name)
                )
        except Exception:
            LOGGER.exception(
                "Channel join process error for user %s", message.from_user.id
            )
            await status.edit_text(
                msgs_chan["request_failed"], reply_markup=main_menu(language)
            )
    finally:
        if out_res and out_res.exists():
            out_res.unlink(missing_ok=True)
        file_path.unlink(missing_ok=True)
        await state.clear()


@router.message(ChannelLeave.waiting_for_file, F.document)
async def receive_channel_leave_file(
    message: Message,
    bot: Bot,
    state: FSMContext,
    settings: Settings,
    session_factory: sessionmaker[Session],
) -> None:
    if message.from_user is None or message.document is None:
        return
    language = user_language(session_factory, message.from_user.id)
    msgs_chan = CHANNEL_MESSAGES.get(language, CHANNEL_MESSAGES["en"])
    path: Path | None = None
    try:
        path, name = await download_document(message, bot, settings, language)
        sessions = await inspect_mergeable_sessions(path)
        if not sessions:
            path.unlink(missing_ok=True)
            await state.clear()
            await message.answer(
                msgs_chan["no_sessions"], reply_markup=main_menu(language)
            )
            return

        await state.update_data(temp_file_path=str(path), original_name=name)
        await state.set_state(ChannelLeave.waiting_for_target)
        fmt = ENTER_CHANNEL_LEAVE_TARGET_PROMPT.get(
            language, ENTER_CHANNEL_LEAVE_TARGET_PROMPT["en"]
        )
        await message.answer(
            fmt.format(count=len(sessions)), reply_markup=cancel_menu(language)
        )
    except Exception as exc:  # noqa: BLE001
        if path is not None:
            path.unlink(missing_ok=True)
        archive_errors = ARCHIVE_ERRORS.get(language, ARCHIVE_ERRORS["en"])
        error = archive_errors.get(str(exc), str(exc))
        await message.answer(
            f"❌ {html.quote(error)}", reply_markup=cancel_menu(language)
        )


@router.message(ChannelLeave.waiting_for_target, F.text)
async def receive_channel_leave_target(
    message: Message,
    state: FSMContext,
    settings: Settings,
    session_factory: sessionmaker[Session],
) -> None:
    if message.from_user is None or not message.text:
        return
    language = user_language(session_factory, message.from_user.id)
    msgs_chan = CHANNEL_MESSAGES.get(language, CHANNEL_MESSAGES["en"])
    data = await state.get_data()
    file_str = data.get("temp_file_path")
    if not file_str:
        await state.clear()
        await message.answer(msgs_chan["no_sessions"], reply_markup=main_menu(language))
        return

    file_path = Path(file_str)
    original_name = data.get("original_name")
    target = message.text.strip()
    if not target or " " in target:
        await message.answer(
            msgs_chan["invalid_target"], reply_markup=cancel_menu(language)
        )
        return
    status = await message.answer(msgs_chan["processing"])
    out_res: Path | None = None
    try:
        try:
            res_chan = await process_channel_leave(
                file_path,
                output_dir=settings.storage_dir / "outbox",
                target=target,
                credentials=settings.api_credential_list,
                original_name=original_name,
            )
            out_res = res_chan.output_path
            if res_chan.success == 0:
                report = msgs_chan["failed_report"].format(failed=res_chan.failed)
            else:
                report = msgs_chan["done"].format(
                    success=res_chan.success, failed=res_chan.failed
                )
            await status.edit_text(
                report,
                reply_markup=channel_result_menu(
                    res_chan.total, res_chan.success, res_chan.failed, language
                ),
            )
            if out_res and out_res.exists():
                await message.answer_document(
                    FSInputFile(out_res, filename=out_res.name)
                )
        except Exception:
            LOGGER.exception(
                "Channel leave process error for user %s", message.from_user.id
            )
            await status.edit_text(
                msgs_chan["request_failed"], reply_markup=main_menu(language)
            )
    finally:
        if out_res and out_res.exists():
            out_res.unlink(missing_ok=True)
        file_path.unlink(missing_ok=True)
        await state.clear()


@router.message(Change2FA.waiting_for_file)
@router.message(Disable2FA.waiting_for_file)
@router.message(Reset2FA.waiting_for_file)
async def two_factor_requires_document(
    message: Message,
    state: FSMContext,
    session_factory: sessionmaker[Session],
) -> None:
    if message.from_user is None:
        return
    language = user_language(session_factory, message.from_user.id)
    current_state = await state.get_state()
    prompts = {
        Change2FA.waiting_for_file.state: CHANGE_2FA_PROMPTS,
        Disable2FA.waiting_for_file.state: DISABLE_2FA_PROMPTS,
        Reset2FA.waiting_for_file.state: RESET_2FA_PROMPTS,
    }
    localized = prompts.get(current_state, CHANGE_2FA_PROMPTS)
    await message.answer(
        EmojiRegistry.enrich(localized.get(language, localized["en"])),
        reply_markup=cancel_menu(language),
    )


@router.message(Change2FA.waiting_for_old_password)
@router.message(Disable2FA.waiting_for_password)
async def two_factor_requires_current_password(
    message: Message,
    state: FSMContext,
    session_factory: sessionmaker[Session],
) -> None:
    if message.from_user is None:
        return
    language = user_language(session_factory, message.from_user.id)
    data = await state.get_data()
    count = int(data.get("session_count", 0))
    prompt = ENTER_CURRENT_2FA_PROMPT.get(language, ENTER_CURRENT_2FA_PROMPT["en"])
    await message.answer(
        EmojiRegistry.enrich(prompt.format(count=count)),
        reply_markup=cancel_menu(language),
    )


@router.message(Change2FA.waiting_for_new_password)
async def two_factor_requires_new_password(
    message: Message, session_factory: sessionmaker[Session]
) -> None:
    if message.from_user is None:
        return
    language = user_language(session_factory, message.from_user.id)
    prompt = ENTER_NEW_2FA_PROMPT.get(language, ENTER_NEW_2FA_PROMPT["en"])
    await message.answer(
        EmojiRegistry.enrich(prompt), reply_markup=cancel_menu(language)
    )


@router.callback_query(F.data == "tool:split")
async def request_split(
    callback: CallbackQuery,
    state: FSMContext,
    session_factory: sessionmaker[Session],
) -> None:
    language = user_language(session_factory, callback.from_user.id)
    await state.set_state(SplitFile.waiting_for_file)
    await callback.answer()
    if isinstance(callback.message, Message):
        await callback.message.edit_text(
            SPLIT_PROMPTS.get(language, SPLIT_PROMPTS["en"]),
            reply_markup=cancel_menu(language),
        )


@router.message(SplitFile.waiting_for_file, F.document)
async def receive_split_file(
    message: Message,
    bot: Bot,
    state: FSMContext,
    settings: Settings,
    session_factory: sessionmaker[Session],
) -> None:
    if message.from_user is None or message.document is None:
        return
    language = user_language(session_factory, message.from_user.id)
    messages = SPLIT_MESSAGES.get(language, SPLIT_MESSAGES["en"])
    path: Path | None = None
    try:
        path, name = await download_document(message, bot, settings, language)
        count = await inspect_session_split(path, original_name=name)
    except (ValueError, UnsafeArchiveError) as exc:
        if path is not None:
            path.unlink(missing_ok=True)
        archive_errors = ARCHIVE_ERRORS.get(language, ARCHIVE_ERRORS["en"])
        error = archive_errors.get(str(exc), str(exc))
        await message.answer(
            f"❌ {html.quote(error)}", reply_markup=cancel_menu(language)
        )
        return

    if count == 0:
        path.unlink(missing_ok=True)
        await state.clear()
        await message.answer(messages["no_sessions"], reply_markup=main_menu(language))
        return

    await state.update_data(
        source_path=str(path),
        original_name=name,
        session_count=count,
    )
    await state.set_state(SplitFile.waiting_for_split_type)
    await message.answer(
        EmojiRegistry.enrich(messages["choose_type"].format(count=count)),
        reply_markup=file_split_choice_menu(language),
    )


@router.message(SplitFile.waiting_for_file)
async def split_requires_document(
    message: Message, session_factory: sessionmaker[Session]
) -> None:
    if message.from_user is None:
        return
    language = user_language(session_factory, message.from_user.id)
    await message.answer(
        SPLIT_PROMPTS.get(language, SPLIT_PROMPTS["en"]),
        reply_markup=cancel_menu(language),
    )


async def _deliver_split_result(
    message: Message,
    status: Message,
    result: SessionSplitResult,
    mode: str,
    language: str,
) -> None:
    messages = SPLIT_MESSAGES.get(language, SPLIT_MESSAGES["en"])
    completed_key = "country_completed" if mode == "country" else "quantity_completed"
    await status.edit_text(
        EmojiRegistry.enrich(
            messages[completed_key].format(total=result.total, groups=result.groups)
        ),
        reply_markup=file_split_result_menu(
            result.total, result.split, result.failed, language
        ),
    )
    caption_key = "caption_country" if mode == "country" else "caption_part"
    for output in result.outputs:
        caption = messages[caption_key].format(
            flag=output.flag or "🌍",
            label=html.quote(output.label),
            count=output.sessions,
        )
        caption = EmojiRegistry.enrich(EmojiRegistry.enrich_flags(caption))
        await message.answer_document(
            FSInputFile(output.path, filename=output.filename), caption=caption
        )


@router.callback_query(
    SplitFile.waiting_for_split_type, F.data.startswith("split_type:")
)
async def choose_split_type(
    callback: CallbackQuery,
    state: FSMContext,
    settings: Settings,
    session_factory: sessionmaker[Session],
) -> None:
    if (
        callback.from_user is None
        or not isinstance(callback.message, Message)
        or callback.data is None
    ):
        return
    language = user_language(session_factory, callback.from_user.id)
    messages = SPLIT_MESSAGES.get(language, SPLIT_MESSAGES["en"])
    mode = callback.data.split(":", 1)[1]
    await callback.answer()

    if mode == "quantity":
        await state.set_state(SplitFile.waiting_for_quantity)
        await callback.message.edit_text(
            EmojiRegistry.enrich(messages["quantity_prompt"]),
            reply_markup=cancel_menu(language),
        )
        return
    if mode != "country":
        return

    data = await state.get_data()
    source = Path(str(data.get("source_path", "")))
    if not source.is_file():
        await state.clear()
        await callback.message.edit_text(
            messages["no_sessions"], reply_markup=main_menu(language)
        )
        return

    output_paths: list[Path] = []
    try:
        await callback.message.edit_text(EmojiRegistry.enrich(messages["splitting"]))
        result = await process_session_split(
            source,
            "country",
            settings.storage_dir / "outbox",
            settings.api_credential_list,
            original_name=str(data.get("original_name", source.name)),
            concurrency=settings.split_concurrency,
        )
        output_paths = [output.path for output in result.outputs]
        await _deliver_split_result(
            callback.message, callback.message, result, "country", language
        )
    except (ValueError, UnsafeArchiveError) as exc:
        archive_errors = ARCHIVE_ERRORS.get(language, ARCHIVE_ERRORS["en"])
        error = archive_errors.get(str(exc), str(exc))
        await callback.message.edit_text(
            f"❌ {html.quote(error)}", reply_markup=main_menu(language)
        )
    except Exception:
        LOGGER.exception("Country split failed for user %s", callback.from_user.id)
        await callback.message.edit_text(
            messages["internal_error"], reply_markup=main_menu(language)
        )
    finally:
        for path in output_paths:
            path.unlink(missing_ok=True)
        source.unlink(missing_ok=True)
        await state.clear()


@router.message(SplitFile.waiting_for_quantity, F.text)
async def split_by_quantity(
    message: Message,
    state: FSMContext,
    settings: Settings,
    session_factory: sessionmaker[Session],
) -> None:
    if message.from_user is None:
        return
    language = user_language(session_factory, message.from_user.id)
    messages = SPLIT_MESSAGES.get(language, SPLIT_MESSAGES["en"])
    try:
        quantity = int((message.text or "").strip())
        if quantity <= 0:
            raise ValueError
    except ValueError:
        await message.answer(
            messages["invalid_quantity"], reply_markup=cancel_menu(language)
        )
        return

    data = await state.get_data()
    source = Path(str(data.get("source_path", "")))
    if not source.is_file():
        await state.clear()
        await message.answer(messages["no_sessions"], reply_markup=main_menu(language))
        return

    status = await message.answer(EmojiRegistry.enrich(messages["splitting"]))
    output_paths: list[Path] = []
    try:
        result = await process_session_split(
            source,
            "quantity",
            settings.storage_dir / "outbox",
            settings.api_credential_list,
            quantity=quantity,
            original_name=str(data.get("original_name", source.name)),
            concurrency=settings.split_concurrency,
        )
        output_paths = [output.path for output in result.outputs]
        await _deliver_split_result(message, status, result, "quantity", language)
    except (ValueError, UnsafeArchiveError) as exc:
        archive_errors = ARCHIVE_ERRORS.get(language, ARCHIVE_ERRORS["en"])
        error = archive_errors.get(str(exc), str(exc))
        await status.edit_text(
            f"❌ {html.quote(error)}", reply_markup=main_menu(language)
        )
    except Exception:
        LOGGER.exception("Quantity split failed for user %s", message.from_user.id)
        await status.edit_text(
            messages["internal_error"], reply_markup=main_menu(language)
        )
    finally:
        for path in output_paths:
            path.unlink(missing_ok=True)
        source.unlink(missing_ok=True)
        await state.clear()


@router.message(SplitFile.waiting_for_quantity)
async def split_requires_quantity(
    message: Message, session_factory: sessionmaker[Session]
) -> None:
    if message.from_user is None:
        return
    language = user_language(session_factory, message.from_user.id)
    messages = SPLIT_MESSAGES.get(language, SPLIT_MESSAGES["en"])
    await message.answer(
        messages["invalid_quantity"], reply_markup=cancel_menu(language)
    )


@router.callback_query(F.data == "split:result:noop")
async def split_result_noop(callback: CallbackQuery) -> None:
    await callback.answer()


@router.callback_query(F.data == "session:result:noop")
async def session_result_noop(callback: CallbackQuery) -> None:
    await callback.answer()


@router.message(ConvertSessionToTdata.waiting_for_file, F.document)
async def process_session_to_tdata_file(
    message: Message,
    bot: Bot,
    state: FSMContext,
    settings: Settings,
    session_factory: sessionmaker[Session],
) -> None:
    if message.from_user is None or message.document is None:
        return
    language = user_language(session_factory, message.from_user.id)
    s2t_msgs = SESSION_TO_TDATA_MESSAGES.get(language, SESSION_TO_TDATA_MESSAGES["en"])
    tool = "s2t"
    user_id = message.from_user.id

    status = await message.answer(s2t_msgs["converting"])
    cancel_event = asyncio.Event()
    progress = JobProgress()
    ACTIVE_CONVERSION_JOBS[(user_id, tool)] = (cancel_event, progress)
    progress_task = asyncio.create_task(
        update_conversion_progress(status, progress, s2t_msgs["converting"], tool, language)
    )

    path: Path | None = None
    output_zip: Path | None = None
    try:
        path, _name = await download_document(message, bot, settings, language)
        started = time.monotonic()
        res = await process_session_to_tdata_conversion(
            path,
            output_dir=settings.storage_dir / "outbox",
            progress=progress,
            cancel_event=cancel_event,
            credentials=settings.api_credential_list,
        )
        elapsed = time.monotonic() - started
        output_zip = res.output_zip_path
        await _stop_progress(progress_task)

        report = (
            f"{s2t_msgs['title']}\n\n"
            + EmojiRegistry.enrich_report(
                _conversion_stats_report(
                    s2t_msgs,
                    res.total,
                    res.converted,
                    res.failed,
                    elapsed,
                    live_verified=bool(settings.api_credential_list),
                )
            )
        )
        if res.converted == 0 or output_zip is None:
            await status.edit_text(
                f"{report}\n\n{s2t_msgs['no_valid_sessions']}",
                reply_markup=main_menu(language),
            )
        else:
            detail_lines = [
                f"{'✅' if entry.ok else '❌'} {html.quote(entry.name)}"
                + ("" if entry.ok else f" — {html.quote(live_failure_label(entry.reason))}")
                for entry in res.entries
            ]
            details, skipped = _truncate_detail_lines(detail_lines)
            if details:
                report = f"{report}\n──────────────\n{details}"
            if skipped:
                report += s2t_msgs["more"].format(count=skipped)
            await status.edit_text(
                report,
                reply_markup=session_to_tdata_result_menu(
                    res.total, res.converted, res.failed, language
                ),
            )
            display_name = "tdata.zip" if res.converted == 1 else "converted_tdatas.zip"
            input_file = FSInputFile(output_zip, filename=display_name)
            await message.answer_document(
                input_file, caption=s2t_msgs.get("caption")
            )
    except JobCancelled:
        await _stop_progress(progress_task)
        await status.edit_text(
            s2t_msgs["cancelled"], reply_markup=main_menu(language)
        )
    except (ValueError, UnsafeArchiveError) as exc:
        await _stop_progress(progress_task)
        err_code = str(exc)
        archive_errs = ARCHIVE_ERRORS.get(language, ARCHIVE_ERRORS["en"])
        err_msg = archive_errs.get(err_code, str(exc))
        await status.edit_text(
            f"❌ {html.quote(err_msg)}", reply_markup=main_menu(language)
        )
    except Exception:
        LOGGER.exception(
            "Session to tdata conversion failed for user %s",
            message.from_user.id,
        )
        await _stop_progress(progress_task)
        await status.edit_text(
            s2t_msgs.get("no_valid_sessions", "❌ Conversion failed."),
            reply_markup=main_menu(language),
        )
    finally:
        ACTIVE_CONVERSION_JOBS.pop((user_id, tool), None)
        if output_zip and output_zip.exists():
            output_zip.unlink(missing_ok=True)
        if path and path.exists():
            path.unlink(missing_ok=True)
        await state.clear()


@router.message(ConvertSessionToTdata.waiting_for_file)
async def session_to_tdata_invalid_input(
    message: Message, session_factory: sessionmaker[Session]
) -> None:
    if message.from_user is None:
        return
    language = user_language(session_factory, message.from_user.id)
    doc_errs = DOWNLOAD_ERRORS.get(language, DOWNLOAD_ERRORS["en"])
    await message.answer(
        doc_errs["document_required"], reply_markup=cancel_menu(language)
    )


@router.message(ConvertTdataToSession.waiting_for_file, F.document)
async def process_tdata_to_session_file(
    message: Message,
    bot: Bot,
    state: FSMContext,
    settings: Settings,
    session_factory: sessionmaker[Session],
) -> None:
    if message.from_user is None or message.document is None:
        return
    language = user_language(session_factory, message.from_user.id)
    t2s_msgs = TDATA_TO_SESSION_MESSAGES.get(language, TDATA_TO_SESSION_MESSAGES["en"])
    tool = "t2s"
    user_id = message.from_user.id

    status = await message.answer(t2s_msgs["converting"])
    cancel_event = asyncio.Event()
    progress = JobProgress()
    ACTIVE_CONVERSION_JOBS[(user_id, tool)] = (cancel_event, progress)
    progress_task = asyncio.create_task(
        update_conversion_progress(status, progress, t2s_msgs["converting"], tool, language)
    )

    path: Path | None = None
    output_file: Path | None = None
    try:
        path, _name = await download_document(message, bot, settings, language)
        started = time.monotonic()
        res = await process_tdata_to_session_conversion(
            path,
            output_dir=settings.storage_dir / "outbox",
            progress=progress,
            cancel_event=cancel_event,
            credentials=settings.api_credential_list,
        )
        elapsed = time.monotonic() - started
        output_file = res.output_path
        await _stop_progress(progress_task)

        report = (
            f"{t2s_msgs['title']}\n\n"
            + EmojiRegistry.enrich_report(
                _conversion_stats_report(
                    t2s_msgs,
                    res.total,
                    res.converted,
                    res.failed,
                    elapsed,
                    live_verified=bool(settings.api_credential_list),
                )
            )
        )
        if res.converted == 0 or output_file is None:
            await status.edit_text(
                f"{report}\n\n{t2s_msgs['no_valid_tdata']}",
                reply_markup=main_menu(language),
            )
        else:
            detail_lines = [
                f"{'✅' if entry.ok else '❌'} {html.quote(entry.name)}"
                + ("" if entry.ok else f" — {html.quote(live_failure_label(entry.reason))}")
                for entry in res.entries
            ]
            details, skipped = _truncate_detail_lines(detail_lines)
            if details:
                report = f"{report}\n──────────────\n{details}"
            if skipped:
                report += t2s_msgs["more"].format(count=skipped)
            await status.edit_text(
                report,
                reply_markup=tdata_to_session_result_menu(
                    res.total, res.converted, res.failed, language
                ),
            )
            display_name = "converted_sessions.zip" if res.is_zip else output_file.name
            input_file = FSInputFile(output_file, filename=display_name)
            await message.answer_document(
                input_file, caption=t2s_msgs.get("caption")
            )
    except JobCancelled:
        await _stop_progress(progress_task)
        await status.edit_text(
            t2s_msgs["cancelled"], reply_markup=main_menu(language)
        )
    except (ValueError, UnsafeArchiveError) as exc:
        await _stop_progress(progress_task)
        err_code = str(exc)
        archive_errs = ARCHIVE_ERRORS.get(language, ARCHIVE_ERRORS["en"])
        err_msg = archive_errs.get(err_code, str(exc))
        await status.edit_text(
            f"❌ {html.quote(err_msg)}", reply_markup=main_menu(language)
        )
    except Exception:
        LOGGER.exception(
            "Tdata to session conversion failed for user %s",
            message.from_user.id,
        )
        await _stop_progress(progress_task)
        await status.edit_text(
            t2s_msgs.get("no_valid_tdata", "❌ Conversion failed."),
            reply_markup=main_menu(language),
        )
    finally:
        ACTIVE_CONVERSION_JOBS.pop((user_id, tool), None)
        if output_file and output_file.exists():
            output_file.unlink(missing_ok=True)
        if path and path.exists():
            path.unlink(missing_ok=True)
        await state.clear()


@router.message(ConvertTdataToSession.waiting_for_file)
async def tdata_to_session_invalid_input(
    message: Message, session_factory: sessionmaker[Session]
) -> None:
    if message.from_user is None:
        return
    language = user_language(session_factory, message.from_user.id)
    doc_errs = DOWNLOAD_ERRORS.get(language, DOWNLOAD_ERRORS["en"])
    await message.answer(
        doc_errs["document_required"], reply_markup=cancel_menu(language)
    )


@router.callback_query(F.data == "account_txt:noop")
async def account_txt_noop(callback: CallbackQuery) -> None:
    await callback.answer()


@router.message(AccountToTxt.waiting_for_file, F.document)
async def process_account_to_txt_file(
    message: Message,
    bot: Bot,
    state: FSMContext,
    settings: Settings,
    session_factory: sessionmaker[Session],
) -> None:
    if message.from_user is None or message.document is None:
        return
    language = user_language(session_factory, message.from_user.id)
    msgs = ACCOUNT_TO_TXT_MESSAGES.get(language, ACCOUNT_TO_TXT_MESSAGES["en"])
    tool = "txt"
    user_id = message.from_user.id
    status = await message.answer(msgs["converting"])
    cancel_event = asyncio.Event()
    progress = JobProgress()
    ACTIVE_CONVERSION_JOBS[(user_id, tool)] = (cancel_event, progress)
    progress_task = asyncio.create_task(
        update_conversion_progress(status, progress, msgs["converting"], tool, language)
    )

    path: Path | None = None
    output_zip: Path | None = None
    try:
        path, original_name = await download_document(message, bot, settings, language)
        result = await process_account_to_txt(
            path,
            settings.storage_dir / "outbox",
            settings.api_credential_list,
            original_name=original_name,
            progress=progress,
            cancel_event=cancel_event,
        )
        output_zip = result.output_zip_path
        await _stop_progress(progress_task)

        report = (
            f"{msgs['title']}\n\n"
            + EmojiRegistry.enrich_report(
                msgs['summary'].format(total=result.total, active=result.active, invalid=result.invalid_converted, failed=result.failed)
            )
            + "\n──────────────"
        )
        detail_lines = [
            f"{'✅' if entry.status == 'active' else ('⚠️' if entry.status == 'invalid' else '❌')} "
            f"{html.quote(entry.name)}"
            + ("" if entry.status == "active" else f" — {html.quote(entry.reason)}")
            for entry in result.entries
        ]
        details, skipped = _truncate_detail_lines(detail_lines)
        if details:
            report = f"{report}\n{details}"
        if skipped:
            report += msgs["more"].format(count=skipped)
        if output_zip is None:
            await status.edit_text(
                f"{report}\n\n{msgs['no_output']}",
                reply_markup=main_menu(language),
            )
        else:
            await status.edit_text(
                report,
                reply_markup=account_txt_result_menu(
                    result.total, result.converted, result.failed, language
                ),
            )
            await message.answer_document(
                FSInputFile(output_zip, filename="account_txt.zip"),
                caption=msgs.get("caption"),
            )
    except JobCancelled:
        await _stop_progress(progress_task)
        await status.edit_text(msgs["cancelled"], reply_markup=main_menu(language))
    except (ValueError, UnsafeArchiveError) as exc:
        await _stop_progress(progress_task)
        archive_errs = ARCHIVE_ERRORS.get(language, ARCHIVE_ERRORS["en"])
        err_msg = archive_errs.get(str(exc), str(exc))
        await status.edit_text(
            f"❌ {html.quote(err_msg)}", reply_markup=main_menu(language)
        )
    except Exception:
        LOGGER.exception("Account to TXT failed for user %s", message.from_user.id)
        await _stop_progress(progress_task)
        await status.edit_text(msgs["no_output"], reply_markup=main_menu(language))
    finally:
        ACTIVE_CONVERSION_JOBS.pop((user_id, tool), None)
        if output_zip is not None:
            output_zip.unlink(missing_ok=True)
        if path is not None:
            path.unlink(missing_ok=True)
        await state.clear()


@router.message(AccountToTxt.waiting_for_file)
async def account_to_txt_invalid_input(
    message: Message, session_factory: sessionmaker[Session]
) -> None:
    if message.from_user is None:
        return
    language = user_language(session_factory, message.from_user.id)
    await message.answer(
        ACCOUNT_TO_TXT_PROMPTS.get(language, ACCOUNT_TO_TXT_PROMPTS["en"]),
        reply_markup=cancel_menu(language),
    )


@router.callback_query(F.data == "session_json:noop")
async def session_json_noop(callback: CallbackQuery) -> None:
    await callback.answer()


@router.message(ConvertSessionToJson.waiting_for_file, F.document)
async def process_session_to_json_file(
    message: Message,
    bot: Bot,
    state: FSMContext,
    settings: Settings,
    session_factory: sessionmaker[Session],
) -> None:
    if message.from_user is None or message.document is None:
        return
    language = user_language(session_factory, message.from_user.id)
    msgs = SESSION_TO_JSON_MESSAGES.get(language, SESSION_TO_JSON_MESSAGES["en"])
    tool = "json"
    user_id = message.from_user.id
    status = await message.answer(msgs["converting"])
    cancel_event = asyncio.Event()
    progress = JobProgress()
    ACTIVE_CONVERSION_JOBS[(user_id, tool)] = (cancel_event, progress)
    progress_task = asyncio.create_task(
        update_conversion_progress(status, progress, msgs["converting"], tool, language)
    )

    path: Path | None = None
    output_zip: Path | None = None
    try:
        path, original_name = await download_document(message, bot, settings, language)
        result = await process_session_to_json(
            path,
            settings.storage_dir / "outbox",
            settings.api_credential_list,
            original_name=original_name,
            progress=progress,
            cancel_event=cancel_event,
        )
        output_zip = result.output_zip_path
        await _stop_progress(progress_task)

        detail_lines = [
            f"{entry.report_icon} {html.quote(entry.profile.identifier)} | "
            f"{html.quote(entry.profile.phone)} | {html.quote(entry.profile.username)}"
            + ("" if entry.authorized else f" — {html.quote(entry.reason)}")
            for entry in result.entries
        ]
        report = (
            f"{msgs['title']}\n\n"
            + EmojiRegistry.enrich_report(
                msgs['summary'].format(total=result.total, active=result.active, invalid=result.invalid_converted, failed=result.failed)
            )
            + "\n──────────────"
        )
        details, skipped = _truncate_detail_lines(detail_lines)
        if details:
            report = f"{report}\n{details}"
        if skipped:
            report += msgs["more"].format(count=skipped)

        if output_zip is None:
            await status.edit_text(
                f"{report}\n\n{msgs['no_output']}",
                reply_markup=main_menu(language),
            )
        else:
            await status.edit_text(
                report,
                reply_markup=session_json_result_menu(
                    result.total, result.converted, result.failed, language
                ),
            )
            await message.answer_document(
                FSInputFile(output_zip, filename="session_json.zip"),
                caption=msgs.get("caption"),
            )
    except JobCancelled:
        await _stop_progress(progress_task)
        await status.edit_text(msgs["cancelled"], reply_markup=main_menu(language))
    except (ValueError, UnsafeArchiveError) as exc:
        await _stop_progress(progress_task)
        archive_errs = ARCHIVE_ERRORS.get(language, ARCHIVE_ERRORS["en"])
        err_msg = archive_errs.get(str(exc), str(exc))
        await status.edit_text(
            f"❌ {html.quote(err_msg)}", reply_markup=main_menu(language)
        )
    except Exception:
        LOGGER.exception("Session to JSON failed for user %s", message.from_user.id)
        await _stop_progress(progress_task)
        await status.edit_text(msgs["no_output"], reply_markup=main_menu(language))
    finally:
        ACTIVE_CONVERSION_JOBS.pop((user_id, tool), None)
        if output_zip is not None:
            output_zip.unlink(missing_ok=True)
        if path is not None:
            path.unlink(missing_ok=True)
        await state.clear()


@router.message(ConvertSessionToJson.waiting_for_file)
async def session_to_json_invalid_input(
    message: Message, session_factory: sessionmaker[Session]
) -> None:
    if message.from_user is None:
        return
    language = user_language(session_factory, message.from_user.id)
    await message.answer(
        SESSION_TO_JSON_PROMPTS.get(language, SESSION_TO_JSON_PROMPTS["en"]),
        reply_markup=cancel_menu(language),
    )


@router.callback_query(F.data == "tool:file_merge")
async def start_file_merge(
    callback: CallbackQuery,
    state: FSMContext,
    session_factory: sessionmaker[Session],
) -> None:
    if callback.from_user is None or not isinstance(callback.message, Message):
        return
    language = user_language(session_factory, callback.from_user.id)
    await state.set_state(FileMerge.waiting_for_file)
    await callback.answer()
    await callback.message.edit_text(
        FILE_MERGE_PROMPTS.get(language, FILE_MERGE_PROMPTS["en"]),
        reply_markup=cancel_menu(language),
    )


@router.callback_query(F.data == "file_merge:noop")
async def file_merge_noop(callback: CallbackQuery) -> None:
    await callback.answer()


@router.message(FileMerge.waiting_for_file, F.document)
async def process_file_merge_file(
    message: Message,
    bot: Bot,
    state: FSMContext,
    settings: Settings,
    session_factory: sessionmaker[Session],
) -> None:
    if message.from_user is None or message.document is None:
        return
    language = user_language(session_factory, message.from_user.id)
    msgs = FILE_MERGE_MESSAGES.get(language, FILE_MERGE_MESSAGES["en"])

    path: Path | None = None
    try:
        path, original_name = await download_document(message, bot, settings, language)
        sessions = await inspect_mergeable_sessions(path)
        count = len(sessions)
        if count == 0:
            await message.answer(msgs["no_sessions"], reply_markup=main_menu(language))
            if path is not None:
                path.unlink(missing_ok=True)
            await state.clear()
            return

        await state.update_data(
            temp_file_path=str(path),
            original_name=original_name,
            session_count=count,
        )
        await state.set_state(FileMerge.waiting_for_merge_type)

        choose_text = EmojiRegistry.enrich(msgs["choose_type"].format(count=count))
        await message.answer(
            choose_text,
            reply_markup=file_merge_choice_menu(language),
        )
    except (ValueError, UnsafeArchiveError) as exc:
        if path is not None:
            path.unlink(missing_ok=True)
        archive_errs = ARCHIVE_ERRORS.get(language, ARCHIVE_ERRORS["en"])
        err_msg = archive_errs.get(str(exc), str(exc))
        await message.answer(
            f"❌ {html.quote(err_msg)}", reply_markup=main_menu(language)
        )
        await state.clear()
    except Exception:
        if path is not None:
            path.unlink(missing_ok=True)
        LOGGER.exception(
            "File merge download/inspect failed for user %s", message.from_user.id
        )
        await message.answer(msgs["no_sessions"], reply_markup=main_menu(language))
        await state.clear()


@router.message(FileMerge.waiting_for_file)
async def file_merge_invalid_input(
    message: Message, session_factory: sessionmaker[Session]
) -> None:
    if message.from_user is None:
        return
    language = user_language(session_factory, message.from_user.id)
    await message.answer(
        FILE_MERGE_PROMPTS.get(language, FILE_MERGE_PROMPTS["en"]),
        reply_markup=cancel_menu(language),
    )


@router.callback_query(
    FileMerge.waiting_for_merge_type, F.data.startswith("merge_type:")
)
async def process_file_merge_choice(
    callback: CallbackQuery,
    state: FSMContext,
    settings: Settings,
    session_factory: sessionmaker[Session],
) -> None:
    if callback.from_user is None or callback.message is None or callback.data is None:
        return
    if not isinstance(callback.message, Message):
        return

    language = user_language(session_factory, callback.from_user.id)
    msgs = FILE_MERGE_MESSAGES.get(language, FILE_MERGE_MESSAGES["en"])
    merge_type = callback.data.split(":", 1)[1]

    data = await state.get_data()
    temp_file_path_str = data.get("temp_file_path")
    if not temp_file_path_str:
        await callback.answer()
        await callback.message.answer(
            msgs["no_sessions"], reply_markup=main_menu(language)
        )
        await state.clear()
        return

    temp_path = Path(temp_file_path_str)
    await callback.answer()

    output_path: Path | None = None
    try:
        await callback.message.edit_text(EmojiRegistry.enrich(msgs["processing"]))

        result = await process_file_merge(
            temp_path,
            merge_type,
            settings.storage_dir / "outbox",
            settings.api_credential_list,
        )

        output_path = result.output_path

        if result.merged == 0 or output_path is None:
            await callback.message.edit_text(
                msgs["no_sessions"], reply_markup=main_menu(language)
            )
            return

        if merge_type == "multi_type":
            report_text = EmojiRegistry.enrich(
                msgs["multi_type_done"].format(merged=result.merged)
            )
            await callback.message.edit_text(
                report_text,
                reply_markup=file_merge_result_menu(
                    result.total, result.merged, result.failed, language
                ),
            )
            await callback.message.answer_document(
                FSInputFile(output_path, filename="merged_all.zip"),
                caption=EmojiRegistry.enrich(msgs["caption_multi_type"]),
            )

        elif merge_type == "session_json_tdata":
            account_lines = "\n".join(
                f"{'✅' if entry.success else '❌'} {html.quote(entry.identifier)}"
                for entry in result.entries
            )
            report_text = EmojiRegistry.enrich(
                f"{msgs['session_json_tdata_done'].format(success=result.merged, failed=result.failed)}\n\n"
                f"{account_lines}"
            )
            await callback.message.edit_text(report_text)
            await callback.message.answer_document(
                FSInputFile(output_path, filename="merge_json_tdata.zip"),
                caption=EmojiRegistry.enrich(msgs["caption_session_json_tdata"]),
            )

    except (ValueError, UnsafeArchiveError) as exc:
        archive_errs = ARCHIVE_ERRORS.get(language, ARCHIVE_ERRORS["en"])
        err_msg = archive_errs.get(str(exc), str(exc))
        await callback.message.edit_text(
            f"❌ {html.quote(err_msg)}", reply_markup=main_menu(language)
        )
    except Exception:
        LOGGER.exception(
            "File merge processing failed for user %s", callback.from_user.id
        )
        await callback.message.edit_text(
            msgs["no_sessions"], reply_markup=main_menu(language)
        )
    finally:
        if output_path is not None:
            output_path.unlink(missing_ok=True)
        if temp_path.exists():
            temp_path.unlink(missing_ok=True)
        await state.clear()


async def _expire_direct_file(
    state: FSMContext,
    prompt: Message,
    token: str,
    language: str,
    *,
    delay: float = _DIRECT_FILE_TIMEOUT_SECONDS,
) -> None:
    await asyncio.sleep(delay)
    if await state.get_state() != DirectFile.waiting_for_action.state:
        return
    data = await state.get_data()
    if data.get("direct_token") != token:
        return

    stored_path = data.get("temp_file_path")
    if stored_path:
        Path(str(stored_path)).unlink(missing_ok=True)
    await state.clear()
    messages = DIRECT_FILE_MESSAGES.get(language, DIRECT_FILE_MESSAGES["en"])
    with suppress(Exception):
        await prompt.edit_text(messages["expired"], reply_markup=main_menu(language))


@router.message(DirectFile.waiting_for_action, F.document)
@router.message(StateFilter(None), F.document)
async def process_direct_document_upload(
    message: Message,
    bot: Bot,
    state: FSMContext,
    settings: Settings,
    session_factory: sessionmaker[Session],
) -> None:
    if message.from_user is None or message.document is None:
        return
    language = user_language(session_factory, message.from_user.id)
    previous = await state.get_data()
    previous_path = previous.get("temp_file_path")
    if previous_path:
        Path(str(previous_path)).unlink(missing_ok=True)
    await state.clear()

    path: Path | None = None
    try:
        path, filename = await download_document(message, bot, settings, language)
        original = Path(filename)
        named_path = path.with_name(
            f"{original.stem}-{path.stem}{original.suffix.lower()}"
        )
        path.replace(named_path)
        path = named_path
        token = uuid4().hex
        await state.set_state(DirectFile.waiting_for_action)
        await state.set_data(
            {
                "temp_file_path": str(path),
                "original_name": filename,
                "direct_token": token,
            }
        )
        prompt_fmt = DIRECT_FILE_PROMPTS.get(language, DIRECT_FILE_PROMPTS["en"])
        prompt = await message.answer(
            prompt_fmt.format(filename=html.quote(filename)),
            reply_markup=quick_action_menu(language),
        )
        asyncio.create_task(_expire_direct_file(state, prompt, token, language))
    except (ValueError, UnsafeArchiveError) as exc:
        if path is not None:
            path.unlink(missing_ok=True)
        archive_errs = ARCHIVE_ERRORS.get(language, ARCHIVE_ERRORS["en"])
        err_msg = archive_errs.get(str(exc), str(exc))
        await message.answer(
            f"❌ {html.quote(err_msg)}", reply_markup=main_menu(language)
        )
    except Exception:
        if path is not None:
            path.unlink(missing_ok=True)
        LOGGER.exception(
            "Direct document upload failed for user %s", message.from_user.id
        )


def _prepare_direct_otp_sessions(
    file_path: Path, original_name: str, settings: Settings
) -> tuple[list[dict[str, str]], Path]:
    work_dir = settings.storage_dir / "inbox" / f"direct_otp_{uuid4().hex}"
    work_dir.mkdir(parents=True, exist_ok=False)
    try:
        if Path(original_name).suffix.lower() == ".session":
            destination = work_dir / safe_filename(original_name)
            shutil.copy2(file_path, destination)
            extracted = [destination]
        elif Path(original_name).suffix.lower() == ".zip":
            extracted = extract_zip_sessions_safe(file_path, work_dir)
        else:
            extracted = []

        sessions: list[dict[str, str]] = []
        for session_path in extracted:
            display_name = session_path.name
            if display_name.startswith("session_"):
                parts = display_name.split("_", 2)
                if len(parts) == 3:
                    display_name = parts[2]
            session_id = Path(display_name).stem
            sessions.append(
                {
                    "session_id": session_id,
                    "user": "N/A",
                    "phone": f"+{session_id}" if session_id.isdigit() else "N/A",
                    "username": "N/A",
                    "session_path": str(session_path),
                }
            )
        return sessions, work_dir
    except Exception:
        shutil.rmtree(work_dir, ignore_errors=True)
        raise


@router.callback_query(DirectFile.waiting_for_action, F.data.startswith("quick:"))
async def process_quick_action(
    callback: CallbackQuery,
    bot: Bot,
    state: FSMContext,
    settings: Settings,
    session_factory: sessionmaker[Session],
) -> None:
    if callback.from_user is None or callback.message is None or callback.data is None:
        return
    if not isinstance(callback.message, Message):
        return

    action = callback.data.split(":", 1)[1]
    language = user_language(session_factory, callback.from_user.id)
    data = await state.get_data()
    temp_file_path_str = data.get("temp_file_path")
    original_name = data.get("original_name", "file.session")

    if not temp_file_path_str or not Path(temp_file_path_str).exists():
        direct_messages = DIRECT_FILE_MESSAGES.get(language, DIRECT_FILE_MESSAGES["en"])
        await callback.answer()
        await callback.message.edit_text(
            direct_messages["expired"],
            reply_markup=main_menu(language),
        )
        await state.clear()
        return

    file_path = Path(temp_file_path_str)
    await callback.answer()
    user_proxy = resolve_user_proxy(session_factory, callback.from_user.id)

    if action in {"session_check", "spam_check"}:
        await state.set_state(AnalyzeFile.waiting_for_file)
        messages = ANALYSIS_MESSAGES.get(language, ANALYSIS_MESSAGES["en"])
        status_message = await callback.message.edit_text(messages["analyzing"])
        if not isinstance(status_message, Message):
            file_path.unlink(missing_ok=True)
            await state.clear()
            return
        progress_task = asyncio.create_task(
            update_progress_bar(status_message, messages["analyzing"])
        )
        try:
            spam_mode = action == "spam_check"
            sess_progress = SessionProgress()
            await _stop_progress(progress_task)
            progress_task = asyncio.create_task(
                update_session_progress(
                    status_message, sess_progress, messages["analyzing"]
                )
            )
            result_check, entries_check = await check_sessions_detailed(
                file_path,
                credentials=settings.api_credential_list,
                timeout=settings.spambot_timeout,
                proxy=user_proxy,
                progress=sess_progress,
            )
            await _stop_progress(progress_task)
            spam_mode = action == "spam_check"
            renderer = render_spam_result if spam_mode else render_session_result
            await status_message.edit_text(
                renderer(result_check, language),
                reply_markup=session_result_menu(
                    result_check, language, spam_mode=spam_mode
                ),
            )
            await _send_status_zips(status_message, file_path, entries_check, language)
        finally:
            await _stop_progress(progress_task)
            file_path.unlink(missing_ok=True)
            await state.clear()

    elif action == "check_contacts":
        await state.set_state(AnalyzeFile.waiting_for_file)
        contact_messages = CHECK_CONTACTS_MESSAGES.get(
            language, CHECK_CONTACTS_MESSAGES["en"]
        )
        status_message = await callback.message.edit_text(contact_messages["checking"])
        if not isinstance(status_message, Message):
            file_path.unlink(missing_ok=True)
            await state.clear()
            return
        cancel_event = asyncio.Event()
        user_id = callback.from_user.id if callback.from_user else 0
        ACTIVE_CONTACTS_JOBS[user_id] = cancel_event
        progress = ContactsProgress()
        progress_task = asyncio.create_task(
            update_contacts_progress(
                status_message, progress, contact_messages["checking"], language
            )
        )
        try:
            try:
                result_contacts = await process_contacts_check(
                    file_path,
                    settings.storage_dir / "outbox",
                    settings.api_credential_list,
                    proxy=user_proxy,
                    concurrency=settings.contacts_check_concurrency,
                    per_session_timeout=settings.contacts_check_timeout,
                    flood_wait_ceiling=settings.contacts_flood_ceiling,
                    progress=progress,
                    cancel_event=cancel_event,
                )
            except ContactsCheckCancelled:
                await _stop_progress(progress_task)
                await status_message.edit_text(
                    EmojiRegistry.enrich_text(
                        f"❌ {html.quote(contact_messages['cancelled'])}"
                    ),
                    reply_markup=main_menu(language),
                )
                await state.clear()
                return
            except (ValueError, UnsafeArchiveError) as exc:
                await _stop_progress(progress_task)
                err_code = str(exc)
                archive_errs = ARCHIVE_ERRORS.get(language, ARCHIVE_ERRORS["en"])
                err_msg = archive_errs.get(err_code, str(exc))
                prompt = CHECK_CONTACTS_PROMPTS.get(
                    language, CHECK_CONTACTS_PROMPTS["en"]
                )
                await status_message.edit_text(
                    f"❌ {html.quote(err_msg)}\n\n{prompt}",
                    reply_markup=cancel_menu(language),
                )
                await state.clear()
                return
            await _stop_progress(progress_task)
            try:
                await status_message.edit_text(
                    render_contacts_result(result_contacts, language),
                    reply_markup=contacts_result_menu(result_contacts, language),
                )
                for zip_path, status_label, count in result_contacts.zip_paths:
                    await status_message.answer_document(
                        FSInputFile(zip_path, filename=zip_path.name),
                        caption=contacts_status_zip_caption(
                            status_label, count, language
                        ),
                    )
                if result_contacts.report_path is not None:
                    await status_message.answer_document(
                        FSInputFile(
                            result_contacts.report_path,
                            filename=result_contacts.report_path.name,
                        ),
                        caption=contacts_report_caption(language),
                    )
            finally:
                for zip_path, _label, _count in result_contacts.zip_paths:
                    zip_path.unlink(missing_ok=True)
                if result_contacts.report_path is not None:
                    result_contacts.report_path.unlink(missing_ok=True)
        finally:
            await _stop_progress(progress_task)
            ACTIVE_CONTACTS_JOBS.pop(user_id, None)
            file_path.unlink(missing_ok=True)
            await state.clear()

    elif action == "read_otp":
        otp_messages = READ_OTP_MESSAGES.get(language, READ_OTP_MESSAGES["en"])
        otp_sessions, work_dir = _prepare_direct_otp_sessions(
            file_path, str(original_name), settings
        )
        file_path.unlink(missing_ok=True)
        if not otp_sessions:
            shutil.rmtree(work_dir, ignore_errors=True)
            await callback.message.edit_text(
                otp_messages["no_sessions"], reply_markup=main_menu(language)
            )
            await state.clear()
            return
        await state.set_state(ReadOTP.viewing_account)
        await state.set_data(
            {
                "otp_sessions": otp_sessions,
                "otp_index": 0,
                "otp_skipped": 0,
                "otp_work_dir": str(work_dir),
            }
        )
        current = otp_sessions[0]
        await callback.message.edit_text(
            otp_messages["account_header"].format(
                current=1,
                total=len(otp_sessions),
                session_id=html.quote(current["session_id"]),
            ),
            reply_markup=otp_initial_menu(language),
        )

    elif action == "file_split":
        count = await inspect_session_split(file_path, original_name=str(original_name))
        if count == 0:
            split_messages = SPLIT_MESSAGES.get(language, SPLIT_MESSAGES["en"])
            await callback.message.edit_text(
                split_messages["no_sessions"], reply_markup=main_menu(language)
            )
            file_path.unlink(missing_ok=True)
            await state.clear()
            return
        await state.set_state(SplitFile.waiting_for_split_type)
        await state.set_data(
            {
                "source_path": str(file_path),
                "original_name": str(original_name),
                "session_count": count,
            }
        )
        split_messages = SPLIT_MESSAGES.get(language, SPLIT_MESSAGES["en"])
        await callback.message.edit_text(
            EmojiRegistry.enrich(split_messages["choose_type"].format(count=count)),
            reply_markup=file_split_choice_menu(language),
        )

    elif action == "file_merge":
        merge_sessions = await inspect_mergeable_sessions(file_path)
        count = len(merge_sessions)
        if count == 0:
            msgs = FILE_MERGE_MESSAGES.get(language, FILE_MERGE_MESSAGES["en"])
            await callback.message.edit_text(
                msgs["no_sessions"], reply_markup=main_menu(language)
            )
            file_path.unlink(missing_ok=True)
            await state.clear()
            return

        await state.set_state(FileMerge.waiting_for_merge_type)
        await state.set_data(
            {
                "temp_file_path": str(file_path),
                "original_name": original_name,
                "session_count": count,
            }
        )
        msgs = FILE_MERGE_MESSAGES.get(language, FILE_MERGE_MESSAGES["en"])
        await callback.message.edit_text(
            EmojiRegistry.enrich(msgs["choose_type"].format(count=count)),
            reply_markup=file_merge_choice_menu(language),
        )

    elif action == "session_to_tdata":
        await state.set_state(ConvertSessionToTdata.waiting_for_file)
        msgs = SESSION_TO_TDATA_MESSAGES.get(language, SESSION_TO_TDATA_MESSAGES["en"])
        status = await callback.message.edit_text(msgs["converting"])
        if not isinstance(status, Message):
            file_path.unlink(missing_ok=True)
            await state.clear()
            return
        tool = "s2t"
        cancel_event = asyncio.Event()
        progress = JobProgress()
        ACTIVE_CONVERSION_JOBS[(callback.from_user.id, tool)] = (cancel_event, progress)
        progress_task = asyncio.create_task(
            update_conversion_progress(status, progress, msgs["converting"], tool, language)
        )
        tdata_zip: Path | None = None
        try:
            started = time.monotonic()
            result_tdata = await process_session_to_tdata_conversion(
                file_path,
                settings.storage_dir / "outbox",
                progress=progress,
                cancel_event=cancel_event,
                credentials=settings.api_credential_list,
            )
            elapsed = time.monotonic() - started
            tdata_zip = result_tdata.output_zip_path
            await _stop_progress(progress_task)
            report = (
                f"{msgs['title']}\n\n"
                + EmojiRegistry.enrich_report(
                    _conversion_stats_report(
                        msgs,
                        result_tdata.total,
                        result_tdata.converted,
                        result_tdata.failed,
                        elapsed,
                        live_verified=bool(settings.api_credential_list),
                    )
                )
            )
            detail_lines = [
                f"{'✅' if entry.ok else '❌'} {html.quote(entry.name)}"
                + ("" if entry.ok else f" — {html.quote(live_failure_label(entry.reason))}")
                for entry in result_tdata.entries
            ]
            details, skipped = _truncate_detail_lines(detail_lines)
            if details:
                report = f"{report}\n──────────────\n{details}"
            if skipped:
                report += msgs["more"].format(count=skipped)
            if tdata_zip is None:
                await status.edit_text(
                    f"{report}\n\n{msgs['no_valid_sessions']}", reply_markup=main_menu(language)
                )
            else:
                await status.edit_text(
                    report,
                    reply_markup=session_to_tdata_result_menu(
                        result_tdata.total,
                        result_tdata.converted,
                        result_tdata.failed,
                        language,
                    ),
                )
                await callback.message.answer_document(
                    FSInputFile(tdata_zip, filename="tdata.zip"),
                    caption=msgs.get("caption"),
                )
        except JobCancelled:
            await _stop_progress(progress_task)
            await status.edit_text(msgs["cancelled"], reply_markup=main_menu(language))
        except Exception:
            LOGGER.exception(
                "Direct session-to-tdata conversion failed for user %s",
                callback.from_user.id,
            )
            await _stop_progress(progress_task)
            await status.edit_text(
                msgs["no_valid_sessions"], reply_markup=main_menu(language)
            )
        finally:
            ACTIVE_CONVERSION_JOBS.pop((callback.from_user.id, tool), None)
            with suppress(Exception):
                await _stop_progress(progress_task)
            if tdata_zip is not None:
                tdata_zip.unlink(missing_ok=True)
            file_path.unlink(missing_ok=True)
            await state.clear()

    elif action == "tdata_to_session":
        await state.set_state(ConvertTdataToSession.waiting_for_file)
        msgs = TDATA_TO_SESSION_MESSAGES.get(language, TDATA_TO_SESSION_MESSAGES["en"])
        status = await callback.message.edit_text(msgs["converting"])
        if not isinstance(status, Message):
            file_path.unlink(missing_ok=True)
            await state.clear()
            return
        tool = "t2s"
        cancel_event = asyncio.Event()
        progress = JobProgress()
        ACTIVE_CONVERSION_JOBS[(callback.from_user.id, tool)] = (cancel_event, progress)
        progress_task = asyncio.create_task(
            update_conversion_progress(status, progress, msgs["converting"], tool, language)
        )
        session_zip: Path | None = None
        try:
            started = time.monotonic()
            result_sess = await process_tdata_to_session_conversion(
                file_path,
                settings.storage_dir / "outbox",
                progress=progress,
                cancel_event=cancel_event,
                credentials=settings.api_credential_list,
            )
            elapsed = time.monotonic() - started
            session_zip = result_sess.output_path
            await _stop_progress(progress_task)
            report = (
                f"{msgs['title']}\n\n"
                + EmojiRegistry.enrich_report(
                    _conversion_stats_report(
                        msgs,
                        result_sess.total,
                        result_sess.converted,
                        result_sess.failed,
                        elapsed,
                        live_verified=bool(settings.api_credential_list),
                    )
                )
            )
            detail_lines = [
                f"{'✅' if entry.ok else '❌'} {html.quote(entry.name)}"
                + ("" if entry.ok else f" — {html.quote(live_failure_label(entry.reason))}")
                for entry in result_sess.entries
            ]
            details, skipped = _truncate_detail_lines(detail_lines)
            if details:
                report = f"{report}\n──────────────\n{details}"
            if skipped:
                report += msgs["more"].format(count=skipped)
            if session_zip is None:
                await status.edit_text(
                    f"{report}\n\n{msgs['no_valid_tdata']}", reply_markup=main_menu(language)
                )
            else:
                await status.edit_text(
                    report,
                    reply_markup=tdata_to_session_result_menu(
                        result_sess.total,
                        result_sess.converted,
                        result_sess.failed,
                        language,
                    ),
                )
                display_name = (
                    "converted_sessions.zip" if result_sess.is_zip else session_zip.name
                )
                await callback.message.answer_document(
                    FSInputFile(session_zip, filename=display_name),
                    caption=msgs.get("caption"),
                )
        except JobCancelled:
            await _stop_progress(progress_task)
            await status.edit_text(msgs["cancelled"], reply_markup=main_menu(language))
        except Exception:
            LOGGER.exception(
                "Direct tdata-to-session conversion failed for user %s",
                callback.from_user.id,
            )
            await _stop_progress(progress_task)
            await status.edit_text(
                msgs["no_valid_tdata"], reply_markup=main_menu(language)
            )
        finally:
            ACTIVE_CONVERSION_JOBS.pop((callback.from_user.id, tool), None)
            with suppress(Exception):
                await _stop_progress(progress_task)
            if session_zip is not None:
                session_zip.unlink(missing_ok=True)
            file_path.unlink(missing_ok=True)
            await state.clear()

    elif action == "session_to_json":
        await state.set_state(ConvertSessionToJson.waiting_for_file)
        msgs = SESSION_TO_JSON_MESSAGES.get(language, SESSION_TO_JSON_MESSAGES["en"])
        status = await callback.message.edit_text(msgs["converting"])
        if not isinstance(status, Message):
            file_path.unlink(missing_ok=True)
            await state.clear()
            return
        tool = "json"
        cancel_event = asyncio.Event()
        progress = JobProgress()
        ACTIVE_CONVERSION_JOBS[(callback.from_user.id, tool)] = (cancel_event, progress)
        progress_task = asyncio.create_task(
            update_conversion_progress(status, progress, msgs["converting"], tool, language)
        )
        json_zip: Path | None = None
        try:
            result_json = await process_session_to_json(
                file_path,
                settings.storage_dir / "outbox",
                settings.api_credential_list,
                original_name=original_name,
                progress=progress,
                cancel_event=cancel_event,
            )
            json_zip = result_json.output_zip_path
            await _stop_progress(progress_task)
            report = (
                f"{msgs['title']}\n\n"
                + EmojiRegistry.enrich_report(
                    msgs['summary'].format(total=result_json.total, active=result_json.active, invalid=result_json.invalid_converted, failed=result_json.failed)
                )
            )
            detail_lines = [
                f"{entry.report_icon} {html.quote(entry.profile.identifier)} | "
                f"{html.quote(entry.profile.phone)} | {html.quote(entry.profile.username)}"
                + ("" if entry.authorized else f" — {html.quote(entry.reason)}")
                for entry in result_json.entries
            ]
            details, skipped = _truncate_detail_lines(detail_lines)
            if details:
                report = f"{report}\n──────────────\n{details}"
            if skipped:
                report += msgs["more"].format(count=skipped)
            if json_zip is None:
                await status.edit_text(
                    f"{report}\n\n{msgs['no_output']}", reply_markup=main_menu(language)
                )
            else:
                await status.edit_text(
                    report,
                    reply_markup=session_json_result_menu(
                        result_json.total,
                        result_json.converted,
                        result_json.failed,
                        language,
                    ),
                )
                await callback.message.answer_document(
                    FSInputFile(json_zip, filename="session_json.zip"),
                    caption=msgs.get("caption"),
                )
        except JobCancelled:
            await _stop_progress(progress_task)
            await status.edit_text(msgs["cancelled"], reply_markup=main_menu(language))
        except Exception:
            LOGGER.exception(
                "Direct session-to-json conversion failed for user %s",
                callback.from_user.id,
            )
            await _stop_progress(progress_task)
            await status.edit_text(msgs["no_output"], reply_markup=main_menu(language))
        finally:
            ACTIVE_CONVERSION_JOBS.pop((callback.from_user.id, tool), None)
            with suppress(Exception):
                await _stop_progress(progress_task)
            if json_zip is not None:
                json_zip.unlink(missing_ok=True)
            file_path.unlink(missing_ok=True)
            await state.clear()

    elif action == "account_to_txt":
        await state.set_state(AccountToTxt.waiting_for_file)
        msgs = ACCOUNT_TO_TXT_MESSAGES.get(language, ACCOUNT_TO_TXT_MESSAGES["en"])
        status = await callback.message.edit_text(msgs["converting"])
        if not isinstance(status, Message):
            file_path.unlink(missing_ok=True)
            await state.clear()
            return
        tool = "a2t"
        cancel_event = asyncio.Event()
        progress = JobProgress()
        ACTIVE_CONVERSION_JOBS[(callback.from_user.id, tool)] = (cancel_event, progress)
        progress_task = asyncio.create_task(
            update_conversion_progress(status, progress, msgs["converting"], tool, language)
        )
        txt_out: Path | None = None
        try:
            result_txt = await process_account_to_txt(
                file_path,
                output_dir=settings.storage_dir / "outbox",
                credentials=settings.api_credential_list,
                original_name=str(original_name),
                progress=progress,
                cancel_event=cancel_event,
            )
            txt_out = result_txt.output_zip_path
            await _stop_progress(progress_task)
            report = (
                f"{msgs['title']}\n\n"
                + EmojiRegistry.enrich_report(
                    msgs['summary'].format(total=result_txt.total, active=result_txt.active, invalid=result_txt.invalid_converted, failed=result_txt.failed)
                )
                + "\n──────────────"
            )
            detail_lines = [
                f"{entry.report_icon} {html.quote(entry.profile.identifier)} | "
                f"{html.quote(entry.profile.phone)} | {html.quote(entry.profile.username)}"
                + ("" if entry.authorized else f" — {html.quote(entry.reason)}")
                for entry in result_txt.entries
            ]
            details, skipped = _truncate_detail_lines(detail_lines)
            if details:
                report = f"{report}\n{details}"
            if skipped:
                report += msgs["more"].format(count=skipped)
            if txt_out is None:
                await status.edit_text(
                    f"{report}\n\n{msgs['no_output']}",
                    reply_markup=main_menu(language),
                )
            else:
                await status.edit_text(
                    report,
                    reply_markup=account_txt_result_menu(
                        result_txt.total,
                        result_txt.converted,
                        result_txt.failed,
                        language,
                    ),
                )
                await callback.message.answer_document(
                    FSInputFile(txt_out, filename="account_txt.zip"),
                    caption=msgs.get("caption"),
                )
        except JobCancelled:
            await _stop_progress(progress_task)
            await status.edit_text(msgs["cancelled"], reply_markup=main_menu(language))
        except Exception:
            LOGGER.exception(
                "Direct account-to-txt conversion failed for user %s",
                callback.from_user.id,
            )
            await _stop_progress(progress_task)
            await status.edit_text(msgs["no_output"], reply_markup=main_menu(language))
        finally:
            ACTIVE_CONVERSION_JOBS.pop((callback.from_user.id, tool), None)
            with suppress(Exception):
                await _stop_progress(progress_task)
            if txt_out and txt_out.exists():
                txt_out.unlink(missing_ok=True)
            file_path.unlink(missing_ok=True)
            await state.clear()

    elif action in ("change_2fa", "disable_2fa"):
        sessions = await inspect_mergeable_sessions(file_path)
        msgs_2fa = TWO_FACTOR_MESSAGES.get(language, TWO_FACTOR_MESSAGES["en"])
        if not sessions:
            file_path.unlink(missing_ok=True)
            await _clear_two_factor_state(state)
            await callback.message.edit_text(
                EmojiRegistry.enrich(msgs_2fa["no_sessions"]),
                reply_markup=main_menu(language),
            )
            return
        if not isinstance(callback.message, Message):
            file_path.unlink(missing_ok=True)
            await _clear_two_factor_state(state)
            return

        operation = "changed" if action == "change_2fa" else "disabled"
        await state.update_data(flow_message_id=callback.message.message_id)
        await _begin_two_factor_batch(
            file_path,
            original_name,
            operation,
            callback.message,
            bot,
            state,
            language,
        )

    elif action == "reset_2fa":
        await state.set_state(Reset2FA.waiting_for_file)
        msgs_2fa = TWO_FACTOR_MESSAGES.get(language, TWO_FACTOR_MESSAGES["en"])
        status = await callback.message.edit_text(
            EmojiRegistry.enrich(msgs_2fa["processing"])
        )
        if not isinstance(status, Message):
            file_path.unlink(missing_ok=True)
            await _clear_two_factor_state(state)
            return
        out_res: Path | None = None
        try:
            res_2fa = await process_reset_2fa(
                file_path,
                settings.storage_dir / "outbox",
                settings.api_credential_list,
                original_name=original_name,
            )
            out_res = res_2fa.output_path
            report = EmojiRegistry.enrich(
                msgs_2fa["done_reset"].format(
                    success=res_2fa.success,
                    pending=res_2fa.pending,
                    failed=res_2fa.failed,
                )
            )
            report += _two_factor_failure_details(res_2fa, language)
            await status.edit_text(
                report,
                reply_markup=two_factor_result_menu(
                    res_2fa.total,
                    res_2fa.success,
                    res_2fa.failed,
                    language,
                    pending=res_2fa.pending,
                ),
            )
            if out_res and out_res.exists():
                suffix = ".zip" if res_2fa.is_zip else ".session"
                await callback.message.answer_document(
                    FSInputFile(
                        out_res,
                        filename=f"2FA_Reset_{res_2fa.success}{suffix}",
                    )
                )
        except Exception:
            LOGGER.exception(
                "Direct 2FA reset failed for user %s", callback.from_user.id
            )
            await status.edit_text(
                EmojiRegistry.enrich(msgs_2fa["request_failed"]),
                reply_markup=main_menu(language),
            )
        finally:
            if out_res and out_res.exists():
                out_res.unlink(missing_ok=True)
            file_path.unlink(missing_ok=True)
            await _clear_two_factor_state(state)

    elif action in ("channel_join", "leave_channel"):
        sessions = await inspect_mergeable_sessions(file_path)
        msgs_chan = CHANNEL_MESSAGES.get(language, CHANNEL_MESSAGES["en"])
        if not sessions:
            file_path.unlink(missing_ok=True)
            await state.clear()
            await callback.message.edit_text(
                msgs_chan["no_sessions"], reply_markup=main_menu(language)
            )
            return

        if action == "channel_join":
            await state.set_state(ChannelJoin.waiting_for_target)
            fmt = ENTER_CHANNEL_JOIN_TARGET_PROMPT.get(
                language, ENTER_CHANNEL_JOIN_TARGET_PROMPT["en"]
            )
        else:
            await state.set_state(ChannelLeave.waiting_for_target)
            fmt = ENTER_CHANNEL_LEAVE_TARGET_PROMPT.get(
                language, ENTER_CHANNEL_LEAVE_TARGET_PROMPT["en"]
            )

        await state.update_data(
            temp_file_path=str(file_path),
            original_name=original_name,
            session_count=len(sessions),
        )
        await callback.message.edit_text(
            fmt.format(count=len(sessions)), reply_markup=cancel_menu(language)
        )

    elif action == "clean_chat":
        if not isinstance(callback.message, Message):
            file_path.unlink(missing_ok=True)
            await state.clear()
            return
        sessions = await inspect_mergeable_sessions(file_path)
        msgs_clean = CLEAN_CHAT_MESSAGES.get(language, CLEAN_CHAT_MESSAGES["en"])
        if not sessions:
            file_path.unlink(missing_ok=True)
            await state.clear()
            await callback.message.edit_text(
                msgs_clean["no_sessions"], reply_markup=main_menu(language)
            )
            return

        await state.set_state(CleanChat.waiting_for_selection)
        await state.update_data(
            temp_file_path=str(file_path),
            original_name=original_name,
            session_count=len(sessions),
            clean_chat_categories=[],
        )
        prompt_fmt = CLEAN_CHAT_MODE_PROMPT.get(language, CLEAN_CHAT_MODE_PROMPT["en"])
        await callback.message.edit_text(
            prompt_fmt.format(count=len(sessions)),
            reply_markup=clean_chat_choice_menu(language, selected=()),
        )

    elif action == "delete_contact":
        if not isinstance(callback.message, Message):
            file_path.unlink(missing_ok=True)
            await state.clear()
            return
        msgs_del = DELETE_CONTACT_MESSAGES.get(language, DELETE_CONTACT_MESSAGES["en"])
        sessions = await inspect_mergeable_sessions(file_path)
        if not sessions:
            file_path.unlink(missing_ok=True)
            await state.clear()
            await callback.message.edit_text(
                msgs_del["no_sessions"], reply_markup=main_menu(language)
            )
            return

        status = await callback.message.edit_text(msgs_del["fetching"])
        if not isinstance(status, Message):
            file_path.unlink(missing_ok=True)
            await state.clear()
            return

        contacts = await fetch_input_contacts(
            file_path,
            settings.api_credential_list,
            original_name=str(original_name),
        )

        if not contacts:
            file_path.unlink(missing_ok=True)
            await state.clear()
            await status.edit_text(
                msgs_del["no_contacts"], reply_markup=main_menu(language)
            )
            return

        contact_dicts = [c.to_dict() for c in contacts]
        await state.set_state(DeleteContact.selecting_contacts)
        await state.update_data(
            temp_file_path=str(file_path),
            original_name=original_name,
            contacts=contact_dicts,
            selected_ids=[],
            page=0,
        )

        fmt = DELETE_CONTACT_SELECT_PROMPT.get(
            language, DELETE_CONTACT_SELECT_PROMPT["en"]
        )
        await status.edit_text(
            fmt.format(count=len(contacts)),
            reply_markup=delete_contact_selection_menu(
                contact_dicts, set(), page=0, language=language
            ),
        )

    elif action == "profile_setup":
        if not isinstance(callback.message, Message):
            file_path.unlink(missing_ok=True)
            await state.clear()
            return
        msgs_prof = PROFILE_SETUP_MESSAGES.get(language, PROFILE_SETUP_MESSAGES["en"])
        sessions = await inspect_mergeable_sessions(file_path)
        if not sessions:
            file_path.unlink(missing_ok=True)
            await state.clear()
            await callback.message.edit_text(
                msgs_prof["no_sessions"], reply_markup=main_menu(language)
            )
            return

        status = await callback.message.edit_text(msgs_prof["fetching"])
        if not isinstance(status, Message):
            file_path.unlink(missing_ok=True)
            await state.clear()
            return

        temp_dir = Path(tempfile.mkdtemp(prefix="ftgc_prof_dir_"))
        extracted_files: list[Path] = []
        if file_path.suffix.lower() == ".zip":
            extracted_files = extract_zip_sessions_safe(file_path, temp_dir)
        else:
            dest = temp_dir / file_path.name
            shutil.copy2(file_path, dest)
            extracted_files = [dest]

        file_path.unlink(missing_ok=True)

        if not extracted_files:
            shutil.rmtree(temp_dir, ignore_errors=True)
            await state.clear()
            await status.edit_text(
                msgs_prof["no_sessions"], reply_markup=main_menu(language)
            )
            return

        await state.set_state(ProfileSetup.managing_account)
        await state.update_data(
            temp_dir=str(temp_dir),
            session_files=[str(f) for f in extracted_files],
            current_index=0,
            modified_count=0,
            skipped_count=0,
            failed_count=0,
            original_name=original_name,
            pending={},
        )

        await _render_profile_setup_current_account(status, state, settings, language)

    elif action == "account_age":
        if not isinstance(callback.message, Message):
            file_path.unlink(missing_ok=True)
            await state.clear()
            return
        msgs_age = ACCOUNT_AGE_MESSAGES.get(language, ACCOUNT_AGE_MESSAGES["en"])
        await state.set_state(AccountAge.waiting_for_file)
        status = await callback.message.edit_text(msgs_age["fetching"])
        if not isinstance(status, Message):
            file_path.unlink(missing_ok=True)
            await state.clear()
            return

        keep_state = False
        try:
            user_proxy = resolve_user_proxy(session_factory, callback.from_user.id)
            res = await process_account_age_check(
                file_path,
                settings.api_credential_list,
                original_name=original_name,
                proxy=user_proxy,
            )

            if res.total == 0 or res.checked == 0 or not res.accounts:
                await status.edit_text(
                    msgs_age["no_sessions"], reply_markup=main_menu(language)
                )
                return

            if len(res.accounts) > 1:
                await state.set_state(AccountAge.viewing_results)
                await state.update_data(
                    accounts=[
                        {
                            "session_name": a.session_name,
                            "user_id": a.user_id,
                            "phone": a.phone,
                            "username": a.username,
                            "first_name": a.first_name,
                            "last_name": a.last_name,
                            "is_premium": a.is_premium,
                            "dc_id": a.dc_id,
                            "creation_estimate": a.creation_estimate,
                            "exact_creation_date": a.exact_creation_date,
                            "is_scam": a.is_scam,
                            "is_fake": a.is_fake,
                            "is_verified": a.is_verified,
                        }
                        for a in res.accounts
                    ],
                    res_total=res.total,
                    res_checked=res.checked,
                    res_failed=res.failed,
                    page=0,
                )
                keep_state = True
            else:
                await state.clear()

            report = format_account_age_report(res, msgs_age, page=0)
            await status.edit_text(
                report,
                reply_markup=account_age_result_menu(
                    res.total,
                    res.checked,
                    res.failed,
                    language,
                    page=0,
                    total_pages=len(res.accounts),
                ),
            )
        except Exception:
            LOGGER.exception(
                "Account age quick process error for user %s",
                callback.from_user.id if callback.from_user else 0,
            )
            with contextlib.suppress(Exception):
                await status.edit_text(
                    msgs_age["request_failed"], reply_markup=main_menu(language)
                )
        finally:
            file_path.unlink(missing_ok=True)
            if not keep_state:
                await state.clear()

    elif action == "kill_sessions":
        if not isinstance(callback.message, Message):
            file_path.unlink(missing_ok=True)
            await state.clear()
            return
        temp_storage = settings.storage_dir / "temp" / f"kill_{uuid4().hex}"
        temp_storage.parent.mkdir(parents=True, exist_ok=True)
        saved_file = temp_storage.with_suffix(
            Path(original_name or file_path.name).suffix
        )
        shutil.copy2(file_path, saved_file)

        await state.set_state(KillSessions.confirming)
        await state.update_data(
            file_path=str(saved_file),
            original_name=original_name,
        )

        confirm_text = KILL_SESSIONS_CONFIRM_PROMPT.get(
            language, KILL_SESSIONS_CONFIRM_PROMPT["en"]
        )
        await callback.message.edit_text(
            confirm_text,
            reply_markup=kill_sessions_confirm_menu(language),
        )
        file_path.unlink(missing_ok=True)
        return

    elif action == "fresh_session":
        if not isinstance(callback.message, Message):
            file_path.unlink(missing_ok=True)
            await state.clear()
            return
        temp_storage = settings.storage_dir / "temp" / f"fresh_{uuid4().hex}"
        temp_storage.parent.mkdir(parents=True, exist_ok=True)
        saved_file = temp_storage.with_suffix(
            Path(original_name or file_path.name).suffix
        )
        shutil.copy2(file_path, saved_file)
        file_path.unlink(missing_ok=True)

        await state.set_state(FreshSession.waiting_for_2fa)
        await state.update_data(
            file_path=str(saved_file),
            original_name=original_name,
        )
        await callback.message.edit_text(
            EmojiRegistry.enrich(
                FRESH_SESSION_2FA_PROMPT.get(language, FRESH_SESSION_2FA_PROMPT["en"])
            ),
            reply_markup=fresh_session_2fa_menu(language),
        )
        return

    elif action == "list_checker":
        if not isinstance(callback.message, Message):
            file_path.unlink(missing_ok=True)
            await state.clear()
            return
        filename = original_name or file_path.name
        temp_dir = Path(tempfile.mkdtemp(prefix="ftgc_list_checker_"))
        saved_file = temp_dir / filename
        shutil.copy2(file_path, saved_file)
        file_path.unlink(missing_ok=True)

        await state.update_data(
            temp_dir=str(temp_dir),
            file1_path=str(saved_file),
            file1_name=filename,
        )
        await state.set_state(ListChecker.waiting_for_file2)
        msgs_lc = LIST_CHECKER_MESSAGES.get(language, LIST_CHECKER_MESSAGES["en"])
        prompt = msgs_lc["file2_prompt"].format(name=html.quote(filename))
        await callback.message.edit_text(
            prompt,
            reply_markup=list_checker_cancel_menu(language),
        )
        return

    elif action == "privacy_settings":
        if not isinstance(callback.message, Message):
            file_path.unlink(missing_ok=True)
            await state.clear()
            return
        filename = original_name or file_path.name
        temp_dir = Path(tempfile.mkdtemp(prefix="ftgc_privacy_"))
        saved_file = temp_dir / filename
        shutil.copy2(file_path, saved_file)
        file_path.unlink(missing_ok=True)

        await state.update_data(
            temp_dir=str(temp_dir),
            file_path=str(saved_file),
            filename=filename,
        )
        await state.set_state(PrivacySettings.selecting_mode)
        msgs_priv = PRIVACY_SETTINGS_MESSAGES.get(
            language, PRIVACY_SETTINGS_MESSAGES["en"]
        )
        await callback.message.edit_text(
            EmojiRegistry.enrich(msgs_priv["prompt_mode"]),
            reply_markup=privacy_mode_menu(language),
        )
        return

    elif action == "clear_contact":
        if not isinstance(callback.message, Message):
            file_path.unlink(missing_ok=True)
            await state.clear()
            return
        msgs_clear = CLEAR_CONTACTS_MESSAGES.get(
            language, CLEAR_CONTACTS_MESSAGES["en"]
        )
        status_msg = await callback.message.edit_text(msgs_clear["processing"])
        if not isinstance(status_msg, Message):
            file_path.unlink(missing_ok=True)
            await state.clear()
            return
        out_clr: Path | None = None
        try:
            user_proxy = resolve_user_proxy(session_factory, callback.from_user.id)
            res_clr = await process_clear_contacts(
                file_path,
                output_dir=settings.storage_dir / "outbox",
                credentials=settings.api_credential_list,
                original_name=original_name,
                proxy=user_proxy,
            )
            out_clr = res_clr.output_path
            if res_clr.cleared == 0:
                report = msgs_clear["failed_report"].format(failed=res_clr.failed)
            else:
                report = msgs_clear["done"].format(
                    success=res_clr.cleared, failed=res_clr.failed
                )
            await status_msg.edit_text(
                report,
                reply_markup=clear_contacts_result_menu(
                    res_clr.total, res_clr.cleared, res_clr.failed, language
                ),
            )
            if out_clr and out_clr.exists():
                await callback.message.answer_document(
                    FSInputFile(out_clr, filename=out_clr.name)
                )
        except Exception:
            LOGGER.exception(
                "Direct clear contacts failed for user %s", callback.from_user.id
            )
            await status_msg.edit_text(
                msgs_clear["request_failed"], reply_markup=main_menu(language)
            )
        finally:
            if out_clr and out_clr.exists():
                out_clr.unlink(missing_ok=True)
            file_path.unlink(missing_ok=True)
            await state.clear()

    elif action == "mass_message":
        if not isinstance(callback.message, Message):
            file_path.unlink(missing_ok=True)
            await state.clear()
            return

        temp_dir = Path(tempfile.mkdtemp(prefix="ftgc_mass_msg_sess_"))
        session_files: list[Path] = []
        suffix = Path(original_name).suffix.lower()

        try:
            if suffix == ".zip":
                session_files = extract_zip_sessions_safe(file_path, Path(temp_dir))
            elif suffix == ".session":
                dest = Path(temp_dir) / Path(original_name).name
                shutil.copy2(file_path, dest)
                session_files = [dest]

            file_path.unlink(missing_ok=True)

            valid_sessions = [
                str(f) for f in session_files if _is_valid_sqlite_session(f)
            ]
            if not valid_sessions:
                shutil.rmtree(temp_dir, ignore_errors=True)
                await state.clear()
                msgs = MASS_MESSAGE_MESSAGES.get(language, MASS_MESSAGE_MESSAGES["en"])
                await callback.message.edit_text(
                    msgs["no_sessions"], reply_markup=main_menu(language)
                )
                return

            await state.set_state(MassMessage.waiting_for_recipients)
            await state.update_data(
                temp_dir=temp_dir,
                session_files=valid_sessions,
            )
            msgs = MASS_MESSAGE_MESSAGES.get(language, MASS_MESSAGE_MESSAGES["en"])
            await callback.message.edit_text(
                msgs["upload_recipients"],
                reply_markup=mass_message_recipients_menu(language),
            )
        except Exception:
            LOGGER.exception("Error processing quick:mass_message")
            shutil.rmtree(temp_dir, ignore_errors=True)
            file_path.unlink(missing_ok=True)
            await state.clear()
            msgs = MASS_MESSAGE_MESSAGES.get(language, MASS_MESSAGE_MESSAGES["en"])
            await callback.message.edit_text(
                msgs["no_sessions"], reply_markup=main_menu(language)
            )

    else:
        direct_messages = DIRECT_FILE_MESSAGES.get(language, DIRECT_FILE_MESSAGES["en"])
        await callback.answer(direct_messages["invalid_action"], show_alert=True)


# ==============================================================================
# MASS MESSAGE HANDLERS
# ==============================================================================


@router.callback_query(F.data == "tool:mass_message")
async def request_mass_message(
    callback: CallbackQuery,
    state: FSMContext,
    session_factory: sessionmaker[Session],
) -> None:
    if callback.from_user is None or not isinstance(callback.message, Message):
        return
    user_id = callback.from_user.id
    language = user_language(session_factory, user_id)
    await callback.answer()

    with session_factory() as db_sess:
        user_record = db_sess.query(User).filter(User.telegram_id == user_id).first()
        if user_record:
            paused_job = (
                db_sess.query(Job)
                .filter(
                    Job.user_id == user_record.id,
                    Job.operation == "mass_message",
                    Job.status == "paused",
                )
                .first()
            )

            if paused_job:
                _ = json.loads(paused_job.options_json or "{}")
                pct = paused_job.progress or 0
                display_id = paused_job.display_id

                prompt_text = ""
                resume_btn_text = ""
                new_btn_text = ""
                cancel_btn_text = ""

                if language == "bn":
                    prompt_text = f"⚠️ আপনার একটি স্থগিত গণ বার্তা কাজ (#{display_id}) রয়েছে যা {pct}% সম্পন্ন হয়েছে।\n\nআপনি কি করতে চান?"
                    resume_btn_text = "▶️ কাজ পুনরায় শুরু করুন"
                    new_btn_text = "➕ নতুন কাজ শুরু করুন"
                    cancel_btn_text = "❌ বাতিল"
                elif language == "hi":
                    prompt_text = f"⚠️ आपके पास एक रुका हुआ सामूहिक संदेश कार्य (#{display_id}) है जो {pct}% पूर्ण हो चुका है।\n\nआप क्या करना चाहेंगे?"
                    resume_btn_text = "▶️ कार्य फिर से शुरू करें"
                    new_btn_text = "➕ नया कार्य शुरू करें"
                    cancel_btn_text = "❌ रद्द करें"
                elif language == "ur":
                    prompt_text = f"⚠️ آپ کے پاس ایک رکا ہوا ماس میسج کام (#{display_id}) ہے جو {pct}% مکمل ہو چکا ہے۔\n\nآپ کیا کرنا چاہیں گے؟"
                    resume_btn_text = "▶️ کام دوبارہ شروع کریں"
                    new_btn_text = "➕ نیا کام شروع کریں"
                    cancel_btn_text = "❌ منسوخ کریں"
                elif language == "ar":
                    prompt_text = f"⚠️ لديك مهمة إرسال رسائل جماعية معلقة (#{display_id}) بنسبة تقدم {pct}%.\n\nماذا تود أن تفعل؟"
                    resume_btn_text = "▶️ استئناف المهمة"
                    new_btn_text = "➕ بدء مهمة جديدة"
                    cancel_btn_text = "❌ إلغاء"
                elif language == "zh":
                    prompt_text = f"⚠️ 您有一个暂停的的群发消息任务 (#{display_id})，进度为 {pct}%。\n\n您想怎么做？"
                    resume_btn_text = "▶️ 恢复任务"
                    new_btn_text = "➕ 开始新任务"
                    cancel_btn_text = "❌ 取消"
                else:  # en
                    prompt_text = f"⚠️ You have a paused mass messaging job (#{display_id}) with {pct}% progress.\n\nWhat would you like to do?"
                    resume_btn_text = "▶️ Resume Job"
                    new_btn_text = "➕ Start New Job"
                    cancel_btn_text = "❌ Cancel"

                keyboard = InlineKeyboardMarkup(
                    inline_keyboard=[
                        [
                            InlineKeyboardButton(
                                text=resume_btn_text,
                                callback_data=f"resume_job:{paused_job.id}",
                                style=ButtonStyle.SUCCESS.value,
                            )
                        ],
                        [
                            InlineKeyboardButton(
                                text=new_btn_text,
                                callback_data="mass_msg_job:new",
                                style=ButtonStyle.PRIMARY.value,
                            )
                        ],
                        [
                            InlineKeyboardButton(
                                text=cancel_btn_text,
                                callback_data="menu:back",
                                style=ButtonStyle.DANGER.value,
                            )
                        ],
                    ]
                )
                await callback.message.edit_text(prompt_text, reply_markup=keyboard)
                return

    # Proceed normally
    await state.set_state(MassMessage.waiting_for_file)
    prompt = MASS_MESSAGE_PROMPTS.get(language, MASS_MESSAGE_PROMPTS["en"])
    await callback.message.edit_text(prompt, reply_markup=cancel_menu(language))


@router.callback_query(F.data == "mass_msg_job:new")
async def start_new_job_callback(
    callback: CallbackQuery,
    state: FSMContext,
    session_factory: sessionmaker[Session],
) -> None:
    if callback.from_user is None or not isinstance(callback.message, Message):
        return
    language = user_language(session_factory, callback.from_user.id)
    await state.set_state(MassMessage.waiting_for_file)
    prompt = MASS_MESSAGE_PROMPTS.get(language, MASS_MESSAGE_PROMPTS["en"])
    await callback.message.edit_text(prompt, reply_markup=cancel_menu(language))


@router.message(MassMessage.waiting_for_file, F.document)
async def receive_mass_message_sessions(
    message: Message,
    bot: Bot,
    state: FSMContext,
    settings: Settings,
    session_factory: sessionmaker[Session],
) -> None:
    if message.from_user is None or message.document is None:
        return
    language = user_language(session_factory, message.from_user.id)
    msgs = MASS_MESSAGE_MESSAGES.get(language, MASS_MESSAGE_MESSAGES["en"])
    temp_dir: str | None = None
    try:
        path, name = await download_document(message, bot, settings, language)
        temp_dir = tempfile.mkdtemp(prefix="ftgc_mass_msg_sess_")
        session_files: list[Path] = []
        suffix = Path(name).suffix.lower()

        if suffix == ".zip":
            session_files = extract_zip_sessions_safe(path, Path(temp_dir))
        elif suffix == ".session":
            dest = Path(temp_dir) / Path(name).name
            shutil.copy2(path, dest)
            session_files = [dest]

        path.unlink(missing_ok=True)

        valid_sessions = [str(f) for f in session_files if _is_valid_sqlite_session(f)]
        if not valid_sessions:
            shutil.rmtree(temp_dir, ignore_errors=True)
            await state.clear()
            await message.answer(msgs["no_sessions"], reply_markup=main_menu(language))
            return

        await state.set_state(MassMessage.waiting_for_recipients)
        await state.update_data(
            temp_dir=temp_dir,
            session_files=valid_sessions,
        )
        await message.answer(
            msgs["upload_recipients"],
            reply_markup=mass_message_recipients_menu(language),
        )
    except Exception:
        LOGGER.exception("Error receiving sessions for Mass Message")
        if temp_dir:
            shutil.rmtree(temp_dir, ignore_errors=True)
        await state.clear()
        await message.answer(msgs["no_sessions"], reply_markup=main_menu(language))


@router.callback_query(
    StateFilter(MassMessage.waiting_for_recipients),
    F.data == "mass_msg_recipients:contacts",
)
async def use_contacts_as_recipients(
    callback: CallbackQuery,
    state: FSMContext,
    settings: Settings,
    session_factory: sessionmaker[Session],
) -> None:
    if callback.from_user is None or not isinstance(callback.message, Message):
        return
    language = user_language(session_factory, callback.from_user.id)
    msgs = MASS_MESSAGE_MESSAGES.get(language, MASS_MESSAGE_MESSAGES["en"])
    await callback.answer()

    with suppress(Exception):
        loading_text = (
            "📇 **استخراج مخاطبین در حال انجام است...**"
            if language == "fa"
            else "📇 **Importing Contacts...**"
        )
        await callback.message.edit_text(loading_text)

    data = await state.get_data()
    session_paths = [Path(p) for p in data.get("session_files", [])]
    extraction_res = await extract_contacts_from_sessions(
        session_paths, settings.api_credential_list
    )
    recipients = extraction_res.recipients
    stats = extraction_res.stats

    if not recipients:
        lines: list[str] = []
        if language == "fa":
            lines.append("❌ **هیچ مخاطب معتبری یافت نشد**\n")
            lines.append(f"📇 **بررسی سشن‌ها ({len(stats)} سشن):**")
            for s in stats:
                if s.status == "no_contacts":
                    lines.append(f"• `{s.session_name}`: ۰ مخاطب ذخیره‌شده")
                elif s.status == "unauthorized":
                    lines.append(f"• `{s.session_name}`: سشن غیرمجاز/منقضی‌شده")
                elif s.status == "invalid_sqlite":
                    lines.append(f"• `{s.session_name}`: دیتابیس سشن نامعتبر")
                else:
                    lines.append(
                        f"• `{s.session_name}`: خطا ({s.error_detail or s.status})"
                    )
            lines.append("\n⚠️ **دلایل احتمالی:**")
            lines.append(
                "• اکانت‌های انتخابی هیچ مخاطب ذخیره‌شده‌ای (Saved Contacts) در دفترچه تلفن تلگرام ندارند."
            )
            lines.append(
                "• مخاطبین فاقد نام کاربری عمومی، شماره تلفن یا آیدی عددی هستند."
            )
            lines.append(
                "\n💡 *می‌توانید به جای آن یک فایل TXT شامل نام‌های کاربری (@username) یا شماره‌ها آپلود کنید.*"
            )
        else:
            lines.append("❌ **No Valid Recipients Found**\n")
            lines.append(f"📇 **Sessions Checked ({len(stats)}):**")
            for s in stats:
                if s.status == "no_contacts":
                    lines.append(f"• `{s.session_name}`: 0 saved contacts")
                elif s.status == "unauthorized":
                    lines.append(
                        f"• `{s.session_name}`: Session unauthorized or revoked"
                    )
                elif s.status == "invalid_sqlite":
                    lines.append(f"• `{s.session_name}`: Invalid session database")
                else:
                    lines.append(
                        f"• `{s.session_name}`: Error ({s.error_detail or s.status})"
                    )
            lines.append("\n⚠️ **Possible Reasons:**")
            lines.append(
                "• Selected account(s) have 0 saved contacts in their Telegram address book."
            )
            lines.append(
                "• Contacts do not have a public username, phone, or Telegram ID."
            )
            lines.append(
                "\n💡 *You can upload a TXT file containing usernames (@username) or phone numbers instead.*"
            )

        await callback.message.edit_text(
            "\n".join(lines),
            reply_markup=mass_message_recipients_menu(language),
        )
        return

    await state.set_state(MassMessage.waiting_for_content)
    await state.update_data(
        recipients=[
            {
                "raw_identifier": r.raw_identifier,
                "recipient_type": r.recipient_type,
                "user_id": r.user_id,
                "username": r.username,
                "phone": r.phone,
            }
            for r in recipients
        ]
    )

    summary_lines: list[str] = []
    if language == "fa":
        summary_lines.append("📇 **گزارش استخراج مخاطبین**\n")
        summary_lines.append(f"👤 **سشن‌های بررسی‌شده ({len(stats)}):**")
        for s in stats:
            if s.status == "ok":
                summary_lines.append(f"• `{s.session_name}`: {s.contacts_found} مخاطب")
            elif s.status == "no_contacts":
                summary_lines.append(f"• `{s.session_name}`: ۰ مخاطب")
            else:
                summary_lines.append(f"• `{s.session_name}`: خطا ({s.status})")
        summary_lines.append(f"\n👥 **مجموع مخاطبین یکتا:** {len(recipients)}\n")
        summary_lines.append(msgs["enter_content"])
    else:
        summary_lines.append("📇 **Contact Import Summary**\n")
        summary_lines.append(f"👤 **Sessions Checked ({len(stats)}):**")
        for s in stats:
            if s.status == "ok":
                summary_lines.append(
                    f"• `{s.session_name}`: {s.contacts_found} contacts"
                )
            elif s.status == "no_contacts":
                summary_lines.append(f"• `{s.session_name}`: 0 contacts")
            else:
                summary_lines.append(f"• `{s.session_name}`: Error ({s.status})")
        summary_lines.append(f"\n👥 **Total Unique Recipients:** {len(recipients)}\n")
        summary_lines.append(msgs["enter_content"])

    await callback.message.edit_text(
        "\n".join(summary_lines), reply_markup=cancel_menu(language)
    )


@router.message(MassMessage.waiting_for_recipients, F.document)
async def receive_recipients_file(
    message: Message,
    bot: Bot,
    state: FSMContext,
    settings: Settings,
    session_factory: sessionmaker[Session],
) -> None:
    if message.from_user is None or message.document is None:
        return
    language = user_language(session_factory, message.from_user.id)
    msgs = MASS_MESSAGE_MESSAGES.get(language, MASS_MESSAGE_MESSAGES["en"])
    path: Path | None = None
    try:
        path, _ = await download_document(message, bot, settings, language)
        recipients = parse_recipients_from_file(path)
        path.unlink(missing_ok=True)

        if not recipients:
            await message.answer(
                msgs["no_recipients"],
                reply_markup=mass_message_recipients_menu(language),
            )
            return

        await state.set_state(MassMessage.waiting_for_content)
        await state.update_data(
            recipients=[
                {
                    "raw_identifier": r.raw_identifier,
                    "recipient_type": r.recipient_type,
                    "user_id": r.user_id,
                    "username": r.username,
                    "phone": r.phone,
                }
                for r in recipients
            ]
        )
        await message.answer(msgs["enter_content"], reply_markup=cancel_menu(language))
    except Exception:
        LOGGER.exception("Error processing recipient file for mass message")
        if path is not None:
            path.unlink(missing_ok=True)
        await message.answer(
            msgs["no_recipients"],
            reply_markup=mass_message_recipients_menu(language),
        )


@router.message(MassMessage.waiting_for_content)
async def receive_mass_message_content(
    message: Message,
    state: FSMContext,
    session_factory: sessionmaker[Session],
) -> None:
    if message.from_user is None:
        return
    language = user_language(session_factory, message.from_user.id)
    msgs = MASS_MESSAGE_MESSAGES.get(language, MASS_MESSAGE_MESSAGES["en"])

    text_content = message.text or message.caption or ""
    media_type = None
    media_file_id = None

    if message.photo:
        media_type = "photo"
        media_file_id = message.photo[-1].file_id
    elif message.video:
        media_type = "video"
        media_file_id = message.video.file_id
    elif message.document:
        media_type = "document"
        media_file_id = message.document.file_id

    await state.set_state(MassMessage.configuring_delay)
    await state.update_data(
        message_text=text_content,
        media_type=media_type,
        media_file_id=media_file_id,
    )
    await message.answer(
        msgs["select_delay"], reply_markup=mass_message_delay_menu(language)
    )


@router.callback_query(
    StateFilter(MassMessage.configuring_delay), F.data.startswith("mass_msg_delay:")
)
async def select_mass_message_delay(
    callback: CallbackQuery,
    state: FSMContext,
    session_factory: sessionmaker[Session],
) -> None:
    if callback.from_user is None or not isinstance(callback.message, Message):
        return
    language = user_language(session_factory, callback.from_user.id)
    msgs = MASS_MESSAGE_MESSAGES.get(language, MASS_MESSAGE_MESSAGES["en"])
    await callback.answer()

    if not callback.data:
        return
    delay_choice = callback.data.split(":", 1)[1]
    if delay_choice == "10_20":
        min_delay, max_delay = 10, 20
        delay_label = "10 - 20s"
    elif delay_choice == "60_120":
        min_delay, max_delay = 60, 120
        delay_label = "60 - 120s"
    else:
        min_delay, max_delay = 20, 60
        delay_label = "20 - 60s"

    data = await state.get_data()
    sessions_count = len(data.get("session_files", []))
    recipients_count = len(data.get("recipients", []))

    await state.set_state(MassMessage.confirming)
    await state.update_data(
        min_delay=min_delay,
        max_delay=max_delay,
        delay_label=delay_label,
    )

    preview_text = msgs["preview_title"].format(
        sessions=sessions_count,
        recipients=recipients_count,
        delay=delay_label,
    )
    await callback.message.edit_text(
        preview_text, reply_markup=mass_message_confirm_menu(language)
    )


async def run_mass_message_job_loop(
    *,
    callback: CallbackQuery,
    bot: Bot,
    state: FSMContext,
    session_factory: sessionmaker[Session],
    settings: Settings,
    user_id: int,
    job_id: str,
    display_id: str,
    session_files: list[Path],
    recipients: list[Recipient],
    message_text: str,
    media_file_id: str | None,
    min_delay: float,
    max_delay: float,
    total: int,
    sent: int,
    failed: int,
    skipped: int,
    details: list[dict[str, Any]],
    status_msg: Message,
    pause_event: asyncio.Event,
    language: str,
    temp_dir_str: str | None = None,
) -> None:
    msgs = MASS_MESSAGE_MESSAGES.get(language, MASS_MESSAGE_MESSAGES["en"])
    media_file_path: Path | None = None
    clients: list[tuple[Any, Path, tempfile.TemporaryDirectory[str]]] = []
    last_error_session: str | None = None
    last_error_detail: str | None = None

    await MASS_MESSAGE_SEMAPHORE.acquire()
    try:
        # Download Telegram bot media if present
        if media_file_id:
            file_info = await bot.get_file(media_file_id)
            if file_info.file_path:
                media_file_path = (
                    Path(tempfile.gettempdir()) / f"mass_media_{uuid4().hex[:6]}"
                )
                await bot.download_file(
                    file_info.file_path, destination=media_file_path
                )

        # Initialize Telethon clients for session pool
        for sf in session_files:
            cli, run_sess, tmp = await create_telethon_client_for_session(
                sf, settings.api_credential_list
            )
            if cli and run_sess and tmp:
                clients.append((cli, sf, tmp))

        if not clients:
            completed_set = {d["recipient"] for d in details}
            remaining_recs = [
                r for r in recipients if r.raw_identifier not in completed_set
            ]
            for rec in remaining_recs:
                failed += 1
                details.append(
                    {
                        "recipient": rec.raw_identifier,
                        "session": "None",
                        "status": "FAILED",
                        "details": "UnauthorizedOrInvalidSession",
                    }
                )
        else:
            start_time = time.time()
            queue: asyncio.Queue[Recipient] = asyncio.Queue()
            completed_set = {d["recipient"] for d in details}
            remaining_recs = [
                r for r in recipients if r.raw_identifier not in completed_set
            ]
            for rec in remaining_recs:
                queue.put_nowait(rec)

            lock = asyncio.Lock()
            global_rate_limiter = GlobalRateLimiter(min_interval_seconds=0.1)
            last_ui_update_time = 0.0
            ui_update_interval = 1.5

            async def worker(cli: Any, session_path: Path) -> None:
                nonlocal \
                    sent, \
                    failed, \
                    skipped, \
                    last_ui_update_time, \
                    last_error_session, \
                    last_error_detail
                entity_cache: dict[str, Any] = {}
                flood_until = 0.0

                while not queue.empty():
                    job_info = ACTIVE_MASS_MESSAGE_JOBS.get(user_id, {})
                    if job_info.get("is_stopped"):
                        break

                    # Zero-CPU overhead pause waiting using asyncio.Event
                    await pause_event.wait()

                    if job_info.get("is_stopped"):
                        break

                    now = time.time()
                    if now < flood_until:
                        wait_sec = flood_until - now
                        await asyncio.sleep(min(wait_sec, 2.0))
                        continue

                    try:
                        rec = queue.get_nowait()
                    except asyncio.QueueEmpty:
                        break

                    await global_rate_limiter.acquire()

                    st, detail = await send_mass_message_to_recipient(
                        cli,
                        rec,
                        message_text,
                        media_file_path,
                        entity_cache=entity_cache,
                    )

                    is_disabled = False
                    if st == "SKIPPED":
                        if "FloodWait" in detail:
                            try:
                                sec_str = (
                                    detail.replace("FloodWait", "")
                                    .replace("s", "")
                                    .strip()
                                )
                                sec = float(sec_str)
                                flood_until = time.time() + sec
                            except Exception:  # noqa: BLE001
                                flood_until = time.time() + 60.0
                        elif detail in ("PeerFlood", "SessionRevoked"):
                            is_disabled = True

                    async with lock:
                        if st == "SENT":
                            sent += 1
                        elif st == "SKIPPED":
                            skipped += 1
                            last_error_session = session_path.name
                            last_error_detail = detail
                        else:
                            failed += 1
                            last_error_session = session_path.name
                            last_error_detail = detail

                        details.append(
                            {
                                "recipient": rec.raw_identifier,
                                "session": session_path.name,
                                "status": st,
                                "details": detail,
                            }
                        )

                        processed_count = sent + failed + skipped
                        pct = int((processed_count / total) * 100) if total > 0 else 100
                        remaining = total - processed_count

                        now_ui = time.time()
                        if (
                            now_ui - last_ui_update_time >= ui_update_interval
                            or processed_count == total
                        ):
                            last_ui_update_time = now_ui
                            # Periodic DB Checkpoint
                            with suppress(Exception), session_factory() as db_sess:
                                j = db_sess.query(Job).filter(Job.id == job_id).first()
                                if j:
                                    j.progress = pct
                                    curr_opt = json.loads(j.options_json or "{}")
                                    curr_completed_set = {
                                        d["recipient"] for d in details
                                    }
                                    curr_opt.update(
                                        {
                                            "sent": sent,
                                            "failed": failed,
                                            "skipped": skipped,
                                            "processed_count": processed_count,
                                            "pending_recipients": [
                                                r.raw_identifier
                                                for r in recipients
                                                if r.raw_identifier
                                                not in curr_completed_set
                                            ],
                                            "completed_recipients": list(
                                                curr_completed_set
                                            ),
                                            "details": details,
                                        }
                                    )
                                    j.options_json = json.dumps(curr_opt)
                                    db_sess.commit()

                            with suppress(Exception):
                                if isinstance(status_msg, Message):
                                    await status_msg.edit_text(
                                        msgs["live_progress"].format(
                                            progress=processed_count,
                                            total=total,
                                            percentage=pct,
                                            sent=sent,
                                            failed=failed,
                                            skipped=skipped,
                                            remaining=remaining,
                                            status_text=msgs["status_running"],
                                        ),
                                        reply_markup=mass_message_live_menu(
                                            is_paused=False, language=language
                                        ),
                                    )

                    queue.task_done()

                    if is_disabled:
                        LOGGER.warning(
                            "Disabling session %s due to %s", session_path.name, detail
                        )
                        break

                    delay = random.uniform(min_delay, max_delay)
                    await asyncio.sleep(delay)

            worker_tasks = [
                asyncio.create_task(worker(cli, sf)) for cli, sf, _ in clients
            ]
            await asyncio.gather(*worker_tasks, return_exceptions=True)

    except Exception:
        LOGGER.exception("Mass message loop error")
    finally:
        MASS_MESSAGE_SEMAPHORE.release()
        duration_seconds = (
            max(1.0, time.time() - start_time) if "start_time" in locals() else 1.0
        )

        processed_count = sent + failed + skipped
        is_interrupted = processed_count < total
        job_info = ACTIVE_MASS_MESSAGE_JOBS.get(user_id, {})
        is_stopped = job_info.get("is_stopped", False)
        is_paused_state = is_interrupted and not is_stopped

        # Update Job status in DB
        with session_factory() as db_sess:
            j = db_sess.query(Job).filter(Job.id == job_id).first()
            if j:
                if is_interrupted:
                    j.status = "stopped" if is_stopped else "paused"
                    j.progress = (
                        int((processed_count / total) * 100) if total > 0 else 0
                    )

                    curr_opt = json.loads(j.options_json or "{}")
                    curr_completed_set = {d["recipient"] for d in details}
                    curr_opt.update(
                        {
                            "sent": sent,
                            "failed": failed,
                            "skipped": skipped,
                            "processed_count": processed_count,
                            "last_error_session": last_error_session,
                            "last_error_detail": last_error_detail,
                            "pending_recipients": [
                                r.raw_identifier
                                for r in recipients
                                if r.raw_identifier not in curr_completed_set
                            ],
                            "completed_recipients": list(curr_completed_set),
                            "details": details,
                        }
                    )
                    j.options_json = json.dumps(curr_opt)
                    db_sess.commit()
                else:
                    finish_job(
                        db_sess,
                        j,
                        error_code=None
                        if (sent > 0 or total == 0)
                        else "MASS_MSG_FAILED",
                    )

        ACTIVE_MASS_MESSAGE_JOBS.pop(user_id, None)

        # Clean up Telethon clients safely in finally block
        for cli, _, tmp in clients:
            with suppress(Exception):
                await cli.disconnect()
            if tmp:
                with suppress(Exception):
                    tmp.cleanup()

        if media_file_path and media_file_path.exists():
            media_file_path.unlink(missing_ok=True)

        if temp_dir_str and not is_paused_state:
            shutil.rmtree(temp_dir_str, ignore_errors=True)

        report_tmp = (
            Path(tempfile.gettempdir()) / f"mass_message_report_{uuid4().hex[:6]}.csv"
        )
        generate_mass_message_report(details, report_tmp, format_type="csv")

        final_status = "completed"
        if is_interrupted:
            final_status = "stopped" if is_stopped else "paused"
        elif sent == 0 and total > 0:
            final_status = "failed"

        summary_text = format_mass_message_summary(
            job_id=display_id,
            accounts_count=len(clients),
            total_recipients=total,
            sent=sent,
            failed=failed,
            skipped=skipped,
            duration_seconds=duration_seconds,
            language=language,
            status=final_status,
            last_error_session=last_error_session,
            last_error_detail=last_error_detail,
        )

        with suppress(Exception):
            if isinstance(status_msg, Message):
                await status_msg.edit_text(summary_text)

                if final_status == "paused":
                    from app.keyboards import mass_message_paused_menu

                    reply_markup = mass_message_paused_menu(
                        job_id=job_id, language=language
                    )
                else:
                    reply_markup = main_menu(language)

                await bot.send_document(
                    chat_id=callback.from_user.id,
                    document=FSInputFile(
                        report_tmp, filename=f"mass_message_report_{display_id}.csv"
                    ),
                    caption=msgs["export_caption"],
                    reply_markup=reply_markup,
                )

        report_tmp.unlink(missing_ok=True)
        await state.clear()


@router.callback_query(
    StateFilter(MassMessage.confirming), F.data == "mass_msg_action:start"
)
async def start_mass_message_execution(
    callback: CallbackQuery,
    bot: Bot,
    state: FSMContext,
    settings: Settings,
    session_factory: sessionmaker[Session],
) -> None:
    if callback.from_user is None or not isinstance(callback.message, Message):
        return
    language = user_language(session_factory, callback.from_user.id)
    msgs = MASS_MESSAGE_MESSAGES.get(language, MASS_MESSAGE_MESSAGES["en"])
    await callback.answer()

    if callback.from_user.id in ACTIVE_MASS_MESSAGE_JOBS:
        await callback.answer(msgs.get("already_active", "⚠️ Job already active."), show_alert=True)
        return

    data = await state.get_data()
    session_files = [Path(p) for p in data.get("session_files", [])]
    raw_recipients = data.get("recipients", [])
    recipients = [Recipient(**item) for item in raw_recipients]
    message_text = data.get("message_text", "")
    media_file_id = data.get("media_file_id")
    min_delay = data.get("min_delay", 20)
    max_delay = data.get("max_delay", 60)
    temp_dir_str = data.get("temp_dir")

    await state.set_state(MassMessage.running)
    await state.update_data(is_paused=False, is_stopped=False)

    status_msg = await callback.message.edit_text(
        msgs["live_progress"].format(
            progress=0,
            total=len(recipients),
            percentage=0,
            sent=0,
            failed=0,
            skipped=0,
            remaining=len(recipients),
            status_text=msgs["status_running"],
        ),
        reply_markup=mass_message_live_menu(is_paused=False, language=language),
    )

    total = len(recipients)
    sent = 0
    failed = 0
    skipped = 0
    details: list[dict[str, Any]] = []

    job_id = str(uuid4())
    pause_event = asyncio.Event()
    pause_event.set()

    user_id = callback.from_user.id

    recipient_list = [rec.raw_identifier for rec in recipients]
    options_dict = {
        "display_id": "",
        "total": total,
        "sent": 0,
        "failed": 0,
        "skipped": 0,
        "pending_recipients": recipient_list,
        "completed_recipients": [],
        "message_text": message_text,
        "media_file_id": media_file_id,
        "session_files": [str(sf) for sf in session_files],
        "min_delay": min_delay,
        "max_delay": max_delay,
    }

    display_id = job_id[:8]
    with session_factory() as db_sess:
        user_record = db_sess.query(User).filter(User.telegram_id == user_id).first()
        if user_record:
            for _ in range(10):
                display_id = generate_unique_display_id(db_sess)
                options_dict["display_id"] = display_id
                db_job = Job(
                    id=job_id,
                    display_id=display_id,
                    user_id=user_record.id,
                    operation="mass_message",
                    input_file_id=None,
                    status="running",
                    progress=0,
                    options_json=json.dumps(options_dict),
                    started_at=utcnow(),
                )
                db_sess.add(db_job)
                try:
                    db_sess.commit()
                    break
                except IntegrityError:
                    db_sess.rollback()
                    continue
            else:
                raise RuntimeError(
                    "Unable to generate unique display_id after 10 attempts."
                )

    ACTIVE_MASS_MESSAGE_JOBS[user_id] = {
        "job_id": job_id,
        "display_id": display_id,
        "pause_event": pause_event,
        "is_stopped": False,
    }

    asyncio.create_task(
        run_mass_message_job_loop(
            callback=callback,
            bot=bot,
            state=state,
            session_factory=session_factory,
            settings=settings,
            user_id=user_id,
            job_id=job_id,
            display_id=display_id,
            session_files=session_files,
            recipients=recipients,
            message_text=message_text,
            media_file_id=media_file_id,
            min_delay=min_delay,
            max_delay=max_delay,
            total=total,
            sent=sent,
            failed=failed,
            skipped=skipped,
            details=details,
            status_msg=status_msg,  # type: ignore[arg-type]
            pause_event=pause_event,
            language=language,
            temp_dir_str=temp_dir_str,
        )
    )


@router.callback_query(F.data.startswith("resume_job:"))
async def resume_job_callback(
    callback: CallbackQuery,
    bot: Bot,
    state: FSMContext,
    settings: Settings,
    session_factory: sessionmaker[Session],
) -> None:
    if callback.from_user is None or not isinstance(callback.message, Message):
        return
    user_id = callback.from_user.id
    language = user_language(session_factory, user_id)
    msgs = MASS_MESSAGE_MESSAGES.get(language, MASS_MESSAGE_MESSAGES["en"])

    if user_id in ACTIVE_MASS_MESSAGE_JOBS:
        alert_text = (
            "⚠️ You already have an active mass messaging job running."
            if language == "en"
            else (
                "⚠️ আপনার একটি সক্রিয় গণ বার্তা কাজ চলছে।"
                if language == "bn"
                else (
                    "⚠️ आपके पास पहले से ही एक सक्रिय कार्य चल रहा है।"
                    if language == "hi"
                    else (
                        "⚠️ آپ کا ایک فعال کام پہلے سے چل رہا ہے۔"
                        if language == "ur"
                        else (
                            "⚠️ لديك مهمة نشطة قيد التشغيل بالفعل."
                            if language == "ar"
                            else "⚠️ 您已有一个运行中的任务。"
                        )
                    )
                )
            )
        )
        await callback.answer(alert_text, show_alert=True)
        return

    job_id = (callback.data or "").split(":", 1)[1]
    with session_factory() as db_sess:
        job = db_sess.query(Job).filter(Job.id == job_id).first()
        if not job or job.operation != "mass_message":
            await callback.answer("❌ Job not found.", show_alert=True)
            return

        if job.status != "paused":
            await callback.answer(msgs.get("not_paused", "❌ Job is not paused."), show_alert=True)
            return

        job.status = "running"
        db_sess.commit()

        options = json.loads(job.options_json or "{}")
        display_id = job.display_id

    message_text = options.get("message_text", "")
    media_file_id = options.get("media_file_id")
    session_files = [Path(p) for p in options.get("session_files", []) if Path(p).exists()]

    if not session_files:
        with session_factory() as db_sess:
            job_ref = db_sess.query(Job).filter(Job.id == job_id).first()
            if job_ref:
                job_ref.status = "paused"
                db_sess.commit()
        await callback.answer(msgs.get("sessions_missing", "❌ Session files are missing; job remains paused."), show_alert=True)
        return

    completed_recipients_set = set(options.get("completed_recipients", []))
    pending_recipients_list = options.get("pending_recipients", [])
    all_identifiers = list(completed_recipients_set) + list(pending_recipients_list)

    seen = set()
    unique_identifiers = []
    for r in all_identifiers:
        if r not in seen:
            seen.add(r)
            unique_identifiers.append(r)

    recipients = [
        Recipient(
            raw_identifier=r,
            recipient_type="username"
            if r.startswith("@")
            else ("phone" if r.startswith("+") else "id"),
            username=r.lstrip("@") if r.startswith("@") else None,
            phone=r if r.startswith("+") else None,
            user_id=int(r) if r.isdigit() else None,
        )
        for r in unique_identifiers
    ]

    total = options.get("total", len(recipients))
    sent = options.get("sent", 0)
    failed = options.get("failed", 0)
    skipped = options.get("skipped", 0)
    details = options.get("details", [])
    min_delay = options.get("min_delay", 20)
    max_delay = options.get("max_delay", 60)

    processed_count = sent + failed + skipped
    pct = int((processed_count / total) * 100) if total > 0 else 0
    remaining = total - processed_count

    await state.set_state(MassMessage.running)
    await state.update_data(is_paused=False, is_stopped=False)

    pause_event = asyncio.Event()
    pause_event.set()

    ACTIVE_MASS_MESSAGE_JOBS[user_id] = {
        "job_id": job_id,
        "display_id": display_id,
        "pause_event": pause_event,
        "is_stopped": False,
    }

    status_msg = await callback.message.edit_text(
        msgs["live_progress"].format(
            progress=processed_count,
            total=total,
            percentage=pct,
            sent=sent,
            failed=failed,
            skipped=skipped,
            remaining=remaining,
            status_text=msgs["status_running"],
        ),
        reply_markup=mass_message_live_menu(is_paused=False, language=language),
    )

    temp_dir_str = None
    if session_files:
        temp_dir_str = str(session_files[0].parent)

    asyncio.create_task(
        run_mass_message_job_loop(
            callback=callback,
            bot=bot,
            state=state,
            session_factory=session_factory,
            settings=settings,
            user_id=user_id,
            job_id=job_id,
            display_id=display_id or "",
            session_files=session_files,
            recipients=recipients,
            message_text=message_text,
            media_file_id=media_file_id,
            min_delay=min_delay,
            max_delay=max_delay,
            total=total,
            sent=sent,
            failed=failed,
            skipped=skipped,
            details=details,
            status_msg=status_msg,  # type: ignore[arg-type]
            pause_event=pause_event,
            language=language,
            temp_dir_str=temp_dir_str,
        )
    )
    await callback.answer()


@router.callback_query(
    StateFilter(MassMessage.running), F.data.startswith("mass_msg_ctrl:")
)
async def control_mass_message_execution(
    callback: CallbackQuery,
    state: FSMContext,
    session_factory: sessionmaker[Session],
) -> None:
    if (
        callback.from_user is None
        or not isinstance(callback.message, Message)
        or not callback.data
    ):
        return
    action = callback.data.split(":", 1)[1]
    language = user_language(session_factory, callback.from_user.id)
    msgs = MASS_MESSAGE_MESSAGES.get(language, MASS_MESSAGE_MESSAGES["en"])

    job_info = ACTIVE_MASS_MESSAGE_JOBS.get(callback.from_user.id, {})
    current_job_id = job_info.get("job_id")

    if action == "pause":
        await state.update_data(is_paused=True)
        if "pause_event" in job_info:
            job_info["pause_event"].clear()

        # Update DB Job Status
        if current_job_id:
            with session_factory() as db_sess:
                j = db_sess.query(Job).filter(Job.id == current_job_id).first()
                if j:
                    j.status = "paused"
                    with suppress(Exception):
                        db_sess.commit()

        await callback.answer(msgs.get("status_pausing", msgs["status_paused"]))
        progress_text: str | None = None
        if current_job_id:
            with session_factory() as db_sess:
                j = db_sess.query(Job).filter(Job.id == current_job_id).first()
                if j:
                    opts = json.loads(j.options_json or "{}")
                    sent_n = opts.get("sent", 0)
                    failed_n = opts.get("failed", 0)
                    skipped_n = opts.get("skipped", 0)
                    processed_n = sent_n + failed_n + skipped_n
                    total_n = opts.get("total", processed_n or 1)
                    pct_n = int((processed_n / total_n) * 100) if total_n > 0 else 0
                    progress_text = msgs["live_progress"].format(
                        progress=processed_n,
                        total=total_n,
                        percentage=pct_n,
                        sent=sent_n,
                        failed=failed_n,
                        skipped=skipped_n,
                        remaining=max(0, total_n - processed_n),
                        status_text=msgs["status_paused"],
                    )
        with suppress(Exception):
            if progress_text:
                await callback.message.edit_text(
                    progress_text,
                    reply_markup=mass_message_live_menu(
                        is_paused=True, language=language
                    ),
                )
            else:
                await callback.message.edit_reply_markup(
                    reply_markup=mass_message_live_menu(
                        is_paused=True, language=language
                    )
                )
    elif action == "resume":
        await state.update_data(is_paused=False)
        if "pause_event" in job_info:
            job_info["pause_event"].set()

        # Update DB Job Status
        if current_job_id:
            with session_factory() as db_sess:
                j = db_sess.query(Job).filter(Job.id == current_job_id).first()
                if j:
                    j.status = "running"
                    with suppress(Exception):
                        db_sess.commit()

        await callback.answer(msgs["status_running"])
        with suppress(Exception):
            await callback.message.edit_reply_markup(
                reply_markup=mass_message_live_menu(is_paused=False, language=language)
            )
    elif action == "stop":
        await state.update_data(is_stopped=True)
        if job_info:
            job_info["is_stopped"] = True
            if "pause_event" in job_info:
                job_info["pause_event"].set()

        # Update DB Job Status
        if current_job_id:
            with session_factory() as db_sess:
                j = db_sess.query(Job).filter(Job.id == current_job_id).first()
                if j:
                    j.status = "stopped"
                    with suppress(Exception):
                        db_sess.commit()

        await callback.answer(msgs["status_stopped"])


@router.callback_query(F.data.startswith("quick:"))
async def expired_quick_action(
    callback: CallbackQuery, session_factory: sessionmaker[Session]
) -> None:
    language = user_language(session_factory, callback.from_user.id)
    messages = DIRECT_FILE_MESSAGES.get(language, DIRECT_FILE_MESSAGES["en"])
    await callback.answer(messages["expired"], show_alert=True)
