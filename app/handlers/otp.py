from __future__ import annotations

import logging
import shutil
import zipfile
from contextlib import suppress
from datetime import UTC, datetime
from pathlib import Path

from aiogram import Bot, F, Router, html
from aiogram.exceptions import TelegramBadRequest
from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery, InlineKeyboardMarkup, Message
from sqlalchemy.orm import Session, sessionmaker

from app.config import Settings
from app.db.repositories import get_user_language
from app.handlers.files import download_document
from app.keyboards import cancel_menu, main_menu, otp_checked_menu, otp_initial_menu
from app.locales import ARCHIVE_ERRORS, READ_OTP_MESSAGES, READ_OTP_PROMPTS
from app.otp_results import OTPAccountResult, OTPCode, render_otp_account
from app.services.files import UnsafeArchiveError
from app.services.otp_reader import logout_account_session, read_account_otps
from app.services.proxy import resolve_user_proxy
from app.states import ReadOTP

router = Router(name="otp")
LOGGER = logging.getLogger(__name__)

_MAX_ZIP_MEMBERS = 2_000
_MAX_ZIP_UNCOMPRESSED_BYTES = 512 * 1024 * 1024
_MAX_COMPRESSION_RATIO = 200
_CHUNK_SIZE = 256 * 1024


async def edit_if_changed(
    message: Message, text: str, *, reply_markup: InlineKeyboardMarkup
) -> None:
    try:
        await message.edit_text(text, reply_markup=reply_markup)
    except TelegramBadRequest as exc:
        if "message is not modified" not in str(exc).lower():
            raise


def user_language(session_factory: sessionmaker[Session], user_id: int) -> str:
    with session_factory() as session:
        return get_user_language(session, user_id)


def get_session_metadata(
    path: Path, *, original_name: str | None = None
) -> dict[str, str]:
    display_path = Path(original_name) if original_name else path
    session_id = display_path.stem

    return {
        "session_id": session_id,
        "user": "N/A",
        "phone": f"+{session_id}" if session_id.isdigit() else "N/A",
        "username": "N/A",
    }


def cleanup_session_files(sessions: list[dict[str, str]]) -> None:
    parent_dirs: set[Path] = set()
    for sess in sessions:
        path_str = sess.get("session_path")
        if path_str:
            path = Path(path_str)
            parent_dirs.add(path.parent)
            path.unlink(missing_ok=True)
    for parent in parent_dirs:
        if parent.name.startswith("direct_otp_"):
            with suppress(OSError):
                parent.rmdir()


def extract_zip_sessions(archive_path: Path, storage_dir: Path) -> list[dict[str, str]]:
    results: list[dict[str, str]] = []
    out_dir = storage_dir / "inbox"
    out_dir.mkdir(parents=True, exist_ok=True)

    with zipfile.ZipFile(archive_path, "r") as archive:
        members = archive.infolist()
        if len(members) > _MAX_ZIP_MEMBERS:
            raise UnsafeArchiveError("zip_too_many_members")

        total_uncompressed = 0
        session_members = []
        for info in members:
            member_path = Path(info.filename)
            if member_path.is_absolute() or ".." in member_path.parts:
                raise UnsafeArchiveError("zip_unsafe_path")
            total_uncompressed += info.file_size
            if total_uncompressed > _MAX_ZIP_UNCOMPRESSED_BYTES:
                raise UnsafeArchiveError("zip_uncompressed_limit")
            if info.compress_size > 0:
                ratio = info.file_size / info.compress_size
                if ratio > _MAX_COMPRESSION_RATIO:
                    raise UnsafeArchiveError("zip_suspicious_ratio")
            if member_path.suffix.lower() == ".session":
                session_members.append(info)

        for idx, info in enumerate(session_members):
            dest = out_dir / f"otp_{idx}_{Path(info.filename).name}"
            try:
                with archive.open(info) as src, dest.open("wb") as dst:
                    while True:
                        chunk = src.read(_CHUNK_SIZE)
                        if not chunk:
                            break
                        dst.write(chunk)
                meta = get_session_metadata(dest, original_name=info.filename)
                meta["session_path"] = str(dest)
                results.append(meta)
            except Exception:  # noqa: BLE001
                LOGGER.debug("Failed extracting zip session member %s", info.filename)

    return results


@router.callback_query(F.data == "tool:read_otp")
async def request_read_otp(
    callback: CallbackQuery,
    state: FSMContext,
    session_factory: sessionmaker[Session],
) -> None:
    language = user_language(session_factory, callback.from_user.id)
    await state.clear()
    await state.set_state(ReadOTP.waiting_for_file)
    await callback.answer()
    if isinstance(callback.message, Message):
        await callback.message.edit_text(
            READ_OTP_PROMPTS.get(language, READ_OTP_PROMPTS["en"]),
            reply_markup=cancel_menu(language),
        )


@router.message(ReadOTP.waiting_for_file, F.document)
async def process_otp_document(
    message: Message,
    bot: Bot,
    state: FSMContext,
    settings: Settings,
    session_factory: sessionmaker[Session],
) -> None:
    if message.from_user is None or message.document is None:
        return
    language = user_language(session_factory, message.from_user.id)
    archive_errs = ARCHIVE_ERRORS.get(language, ARCHIVE_ERRORS["en"])

    path: Path | None = None
    try:
        path, name = await download_document(message, bot, settings, language)
        suffix = Path(name).suffix.lower()

        if suffix not in (".session", ".zip"):
            await message.answer(
                READ_OTP_PROMPTS.get(language, READ_OTP_PROMPTS["en"]),
                reply_markup=cancel_menu(language),
            )
            return

        sessions: list[dict[str, str]] = []
        if suffix == ".session":
            inbox_dir = settings.storage_dir / "inbox"
            inbox_dir.mkdir(parents=True, exist_ok=True)
            stored_dest = inbox_dir / f"otp_{path.name}"
            shutil.copy2(path, stored_dest)
            meta = get_session_metadata(stored_dest, original_name=name)
            meta["session_path"] = str(stored_dest)
            sessions = [meta]
        else:
            sessions = extract_zip_sessions(path, settings.storage_dir)

        if not sessions:
            await message.answer(
                msgs_for(language)["no_sessions"],
                reply_markup=cancel_menu(language),
            )
            return

        await state.update_data(
            otp_sessions=sessions,
            otp_index=0,
            otp_skipped=0,
        )
        await state.set_state(ReadOTP.viewing_account)

        msgs = READ_OTP_MESSAGES.get(language, READ_OTP_MESSAGES["en"])
        curr = sessions[0]
        text = msgs["account_header"].format(
            current=1,
            total=len(sessions),
            session_id=html.quote(curr["session_id"]),
        )
        await message.answer(text, reply_markup=otp_initial_menu(language))

    except UnsafeArchiveError as err:
        err_msg = archive_errs.get(err.code, "Archive error")
        await message.answer(err_msg, reply_markup=cancel_menu(language))
    except Exception as exc:
        LOGGER.exception("Error processing OTP document")
        await message.answer(str(exc), reply_markup=cancel_menu(language))
    finally:
        if path:
            path.unlink(missing_ok=True)


@router.callback_query(ReadOTP.viewing_account, F.data == "otp:check")
async def handle_otp_check(
    callback: CallbackQuery,
    state: FSMContext,
    settings: Settings,
    session_factory: sessionmaker[Session],
) -> None:
    language = user_language(session_factory, callback.from_user.id)
    data = await state.get_data()
    sessions: list[dict[str, str]] = data.get("otp_sessions", [])
    index: int = data.get("otp_index", 0)

    if not sessions or index >= len(sessions):
        await callback.answer()
        return

    curr = sessions[index]
    user_val = curr.get("user", "N/A")
    phone_val = curr.get("phone", f"+{curr['session_id']}")
    username_val = curr.get("username", "N/A")
    codes: list[OTPCode] = []

    session_path_str = curr.get("session_path")
    if session_path_str and settings.api_credential_list:
        path = Path(session_path_str)
        user_proxy = resolve_user_proxy(session_factory, callback.from_user.id)
        user_info, live_codes = await read_account_otps(
            path, settings.api_credential_list, proxy=user_proxy
        )
        if user_info.get("user"):
            user_val = user_info["user"]
        if user_info.get("phone"):
            phone_val = user_info["phone"]
        if user_info.get("username"):
            username_val = user_info["username"]
        codes = live_codes

    now_iso = datetime.now(UTC).isoformat()
    await state.update_data(last_check_ts=now_iso)

    result = OTPAccountResult(
        current=index + 1,
        total=len(sessions),
        user=user_val,
        phone=phone_val,
        username=username_val,
        codes=tuple(codes),
        since_last_check=False,
    )
    text = render_otp_account(result, language=language)

    await callback.answer()
    if isinstance(callback.message, Message):
        await edit_if_changed(
            callback.message, text, reply_markup=otp_checked_menu(language)
        )


@router.callback_query(ReadOTP.viewing_account, F.data == "otp:check_again")
async def handle_otp_check_again(
    callback: CallbackQuery,
    state: FSMContext,
    settings: Settings,
    session_factory: sessionmaker[Session],
) -> None:
    language = user_language(session_factory, callback.from_user.id)
    data = await state.get_data()
    sessions: list[dict[str, str]] = data.get("otp_sessions", [])
    index: int = data.get("otp_index", 0)

    if not sessions or index >= len(sessions):
        await callback.answer()
        return

    curr = sessions[index]
    user_val = curr.get("user", "N/A")
    phone_val = curr.get("phone", f"+{curr['session_id']}")
    username_val = curr.get("username", "N/A")
    codes: list[OTPCode] = []

    last_check_str = data.get("last_check_ts")
    since_dt: datetime | None = None
    if last_check_str:
        with suppress(ValueError):
            since_dt = datetime.fromisoformat(last_check_str)

    session_path_str = curr.get("session_path")
    if session_path_str and settings.api_credential_list:
        path = Path(session_path_str)
        user_proxy = resolve_user_proxy(session_factory, callback.from_user.id)
        user_info, live_codes = await read_account_otps(
            path, settings.api_credential_list, since_dt=since_dt, proxy=user_proxy
        )
        if user_info.get("user"):
            user_val = user_info["user"]
        if user_info.get("phone"):
            phone_val = user_info["phone"]
        if user_info.get("username"):
            username_val = user_info["username"]
        codes = live_codes

    now_iso = datetime.now(UTC).isoformat()
    await state.update_data(last_check_ts=now_iso)

    result = OTPAccountResult(
        current=index + 1,
        total=len(sessions),
        user=user_val,
        phone=phone_val,
        username=username_val,
        codes=tuple(codes),
        since_last_check=True,
    )
    text = render_otp_account(result, language=language)

    await callback.answer()
    if isinstance(callback.message, Message):
        await edit_if_changed(
            callback.message, text, reply_markup=otp_checked_menu(language)
        )


@router.callback_query(ReadOTP.viewing_account, F.data == "otp:logout")
async def handle_otp_logout(
    callback: CallbackQuery,
    state: FSMContext,
    settings: Settings,
    session_factory: sessionmaker[Session],
) -> None:
    language = user_language(session_factory, callback.from_user.id)
    data = await state.get_data()
    sessions: list[dict[str, str]] = data.get("otp_sessions", [])
    index: int = data.get("otp_index", 0)

    if sessions and index < len(sessions):
        curr = sessions[index]
        session_path_str = curr.get("session_path")
        if session_path_str and settings.api_credential_list:
            user_proxy = resolve_user_proxy(session_factory, callback.from_user.id)
            await logout_account_session(
                Path(session_path_str), settings.api_credential_list, proxy=user_proxy
            )

    msgs = READ_OTP_MESSAGES.get(language, READ_OTP_MESSAGES["en"])
    await callback.answer(msgs["logged_out"], show_alert=False)

    next_index = index + 1
    total = len(sessions)

    if next_index < total:
        await state.update_data(otp_index=next_index)
        curr = sessions[next_index]
        text = msgs["account_header"].format(
            current=next_index + 1,
            total=total,
            session_id=html.quote(curr["session_id"]),
        )
        if isinstance(callback.message, Message):
            await callback.message.edit_text(
                text, reply_markup=otp_initial_menu(language)
            )
    else:
        cleanup_session_files(sessions)
        await state.clear()
        summary_text = msgs["all_processed"].format(total=total)
        if isinstance(callback.message, Message):
            await callback.message.edit_text(
                summary_text, reply_markup=main_menu(language)
            )


@router.callback_query(ReadOTP.viewing_account, F.data == "otp:skip")
async def handle_otp_skip(
    callback: CallbackQuery,
    state: FSMContext,
    session_factory: sessionmaker[Session],
) -> None:
    language = user_language(session_factory, callback.from_user.id)
    data = await state.get_data()
    sessions: list[dict[str, str]] = data.get("otp_sessions", [])
    index: int = data.get("otp_index", 0)
    skipped: int = data.get("otp_skipped", 0) + 1

    msgs = READ_OTP_MESSAGES.get(language, READ_OTP_MESSAGES["en"])
    await callback.answer()

    next_index = index + 1
    total = len(sessions)

    if next_index < total:
        await state.update_data(otp_index=next_index, otp_skipped=skipped)
        curr = sessions[next_index]
        text = msgs["account_header"].format(
            current=next_index + 1,
            total=total,
            session_id=html.quote(curr["session_id"]),
        )
        if isinstance(callback.message, Message):
            await callback.message.edit_text(
                text, reply_markup=otp_initial_menu(language)
            )
    else:
        cleanup_session_files(sessions)
        await state.clear()
        parts = []
        if skipped > 0:
            parts.append(msgs["skipped_one"].format(count=skipped))
        parts.append(msgs["all_processed"].format(total=total))
        summary_text = "\n\n".join(parts)
        if isinstance(callback.message, Message):
            await callback.message.edit_text(
                summary_text, reply_markup=main_menu(language)
            )


@router.message(ReadOTP.waiting_for_file)
@router.message(ReadOTP.viewing_account)
async def handle_invalid_input(
    message: Message,
    session_factory: sessionmaker[Session],
) -> None:
    if message.from_user is None:
        return
    language = user_language(session_factory, message.from_user.id)
    await message.answer(
        READ_OTP_PROMPTS.get(language, READ_OTP_PROMPTS["en"]),
        reply_markup=cancel_menu(language),
    )


def msgs_for(language: str) -> dict[str, str]:
    return READ_OTP_MESSAGES.get(language, READ_OTP_MESSAGES["en"])
