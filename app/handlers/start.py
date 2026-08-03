import shutil
import urllib.parse
from pathlib import Path

from aiogram import Bot, F, Router, html
from aiogram.filters import Command, CommandStart
from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery, Message
from sqlalchemy.orm import Session, sessionmaker

from app.config import Settings
from app.db.repositories import (
    get_user_language,
    get_user_proxy,
    set_user_language,
    set_user_proxy,
    upsert_user,
)
from app.keyboards import (
    cancel_menu,
    help_support_menu,
    language_menu,
    main_menu,
    membership_menu,
    proxy_menu,
    resolve_support_contact,
)
from app.locales import (
    ENTER_ACCOUNT_AGE_PROMPT,
    HELP_MESSAGES,
    INVALID_LANGUAGE_MESSAGES,
    LANGUAGE_PROMPT,
    LANGUAGE_PROMPTS,
    LANGUAGES,
    PLAN_MESSAGES,
    PRIVACY_MESSAGES,
    PROXY_FAIL_MESSAGES,
    PROXY_INVALID_MESSAGES,
    PROXY_MESSAGES,
    PROXY_REMOVED_MESSAGES,
    PROXY_SUCCESS_MESSAGES,
    PROXY_TESTING_MESSAGES,
    REFERRAL_MESSAGES,
    SUPPORT_UNAVAILABLE,
    action_message,
    get_locale,
    proxy_status_text,
)
from app.services.membership import missing_memberships
from app.states import AccountAge, ProxyState

router = Router(name="start")


async def clear_state_and_file(state: FSMContext) -> None:
    data = await state.get_data()
    for key in ("source_path", "temp_file_path"):
        stored_path = data.get(key)
        if stored_path:
            Path(stored_path).unlink(missing_ok=True)
    otp_sessions = data.get("otp_sessions", [])
    for sess in otp_sessions:
        sp = sess.get("session_path")
        if sp:
            Path(sp).unlink(missing_ok=True)
    otp_work_dir = data.get("otp_work_dir")
    if otp_work_dir:
        shutil.rmtree(Path(otp_work_dir), ignore_errors=True)
    await state.clear()


async def has_access(bot: Bot, user_id: int, settings: Settings) -> bool:
    return not await missing_memberships(bot, user_id, settings.required_channel_list)


def user_language(session_factory: sessionmaker[Session], user_id: int) -> str:
    with session_factory() as session:
        return get_user_language(session, user_id)


@router.message(CommandStart())
async def command_start(
    message: Message,
    bot: Bot,
    state: FSMContext,
    settings: Settings,
    session_factory: sessionmaker[Session],
) -> None:
    if message.from_user is None:
        return
    await clear_state_and_file(state)
    with session_factory() as session:
        user = upsert_user(session, message.from_user.id, message.from_user.username)
        language = user.language

    if language not in LANGUAGES:
        await message.answer(LANGUAGE_PROMPT, reply_markup=language_menu())
        return
    locale = get_locale(language)
    if not await has_access(bot, message.from_user.id, settings):
        channel_names = "\n".join(
            f"📢 {channel}" for channel in settings.required_channel_list
        )
        text = locale.join_required
        if channel_names:
            text = f"{text}\n\n{channel_names}"
        await message.answer(
            text,
            reply_markup=membership_menu(settings.required_channel_list, language),
        )
        return
    await message.answer(
        f"{locale.welcome}\n\n{locale.choose_option}",
        reply_markup=main_menu(language),
    )


@router.message(Command("language"))
async def command_language(
    message: Message,
    session_factory: sessionmaker[Session],
) -> None:
    if message.from_user is None:
        return
    with session_factory() as session:
        language = get_user_language(session, message.from_user.id)
    prompt = LANGUAGE_PROMPTS.get(language, LANGUAGE_PROMPT)
    await message.answer(prompt, reply_markup=language_menu(language))


@router.message(Command("referral"))
async def command_referral(
    message: Message,
    bot: Bot,
    session_factory: sessionmaker[Session],
) -> None:
    if message.from_user is None:
        return
    with session_factory() as session:
        language = get_user_language(session, message.from_user.id)
    bot_info = await bot.get_me()
    bot_username = bot_info.username or "FastTGConvert_bot"
    ref_link = f"https://t.me/{bot_username}?start=ref_{message.from_user.id}"
    template = REFERRAL_MESSAGES.get(language, REFERRAL_MESSAGES["en"])
    msg = template.format(
        ref_link=ref_link,
        user_id=message.from_user.id,
        referred=0,
        earned_days=0,
    )
    await message.answer(msg, disable_web_page_preview=True)


def validate_proxy_url(proxy_str: str) -> str | None:
    if not proxy_str:
        return None
    try:
        parsed = urllib.parse.urlparse(proxy_str)
        if parsed.scheme.lower() not in ("socks5", "socks4", "http", "https"):
            return None
        if not parsed.hostname or not parsed.port:
            return None
        if not (1 <= parsed.port <= 65535):
            return None
        return proxy_str
    except (ValueError, TypeError, AttributeError):
        return None


@router.message(Command("proxy"))
async def command_proxy(
    message: Message,
    session_factory: sessionmaker[Session],
) -> None:
    if message.from_user is None:
        return
    with session_factory() as session:
        language = get_user_language(session, message.from_user.id)
        current_proxy = get_user_proxy(session, message.from_user.id)
    text = proxy_status_text(current_proxy, language)
    kb = proxy_menu(has_proxy=bool(current_proxy), language=language)
    await message.answer(text, reply_markup=kb)


@router.callback_query(F.data == "proxy:set")
async def callback_proxy_set(
    callback: CallbackQuery,
    state: FSMContext,
    session_factory: sessionmaker[Session],
) -> None:
    if not isinstance(callback.message, Message):
        return
    await callback.answer()
    language = user_language(session_factory, callback.from_user.id)
    await state.set_state(ProxyState.waiting_for_proxy)
    prompt = PROXY_MESSAGES.get(language, PROXY_MESSAGES["en"])
    await callback.message.edit_text(prompt, reply_markup=cancel_menu(language))


@router.callback_query(F.data == "proxy:view")
async def callback_proxy_view(
    callback: CallbackQuery,
    session_factory: sessionmaker[Session],
) -> None:
    with session_factory() as session:
        current_proxy = get_user_proxy(session, callback.from_user.id)
    if current_proxy:
        await callback.answer(f"📡 Current Proxy:\n{current_proxy}", show_alert=True)
    else:
        await callback.answer(
            "❌ No custom proxy set. System default proxy will be used.", show_alert=True
        )


@router.callback_query(F.data == "proxy:remove")
async def callback_proxy_remove(
    callback: CallbackQuery,
    session_factory: sessionmaker[Session],
) -> None:
    if not isinstance(callback.message, Message):
        return
    with session_factory() as session:
        set_user_proxy(session, callback.from_user.id, None)
        language = get_user_language(session, callback.from_user.id)
    await callback.answer(
        PROXY_REMOVED_MESSAGES.get(language, PROXY_REMOVED_MESSAGES["en"])
    )
    text = proxy_status_text(None, language)
    kb = proxy_menu(has_proxy=False, language=language)
    await callback.message.edit_text(text, reply_markup=kb)


@router.message(ProxyState.waiting_for_proxy)
async def process_proxy_input(
    message: Message,
    state: FSMContext,
    session_factory: sessionmaker[Session],
) -> None:
    if message.from_user is None:
        return
    with session_factory() as session:
        language = get_user_language(session, message.from_user.id)
    raw_proxy = (message.text or "").strip()
    valid_proxy = validate_proxy_url(raw_proxy)
    if valid_proxy is None:
        msg = PROXY_INVALID_MESSAGES.get(language, PROXY_INVALID_MESSAGES["en"])
        await message.answer(msg, reply_markup=cancel_menu(language))
        return

    from app.services.proxy import parse_telethon_proxy, test_proxy_connection

    testing_template = PROXY_TESTING_MESSAGES.get(
        language, PROXY_TESTING_MESSAGES["en"]
    )
    testing_msg = await message.answer(testing_template)

    parsed_tuple = parse_telethon_proxy(valid_proxy)
    is_ok, detail = await test_proxy_connection(parsed_tuple, timeout=5.0)

    if not is_ok:
        fail_template = PROXY_FAIL_MESSAGES.get(
            language, PROXY_FAIL_MESSAGES["en"]
        )
        fail_msg = fail_template.format(detail=detail)
        if isinstance(testing_msg, Message):
            await testing_msg.edit_text(fail_msg, reply_markup=cancel_menu(language))
        else:
            await message.answer(fail_msg, reply_markup=cancel_menu(language))
        return

    with session_factory() as session:
        set_user_proxy(session, message.from_user.id, valid_proxy)
    await state.clear()
    success_template = PROXY_SUCCESS_MESSAGES.get(
        language, PROXY_SUCCESS_MESSAGES["en"]
    )
    if isinstance(testing_msg, Message):
        await testing_msg.edit_text(
            success_template.format(proxy=valid_proxy),
            reply_markup=proxy_menu(has_proxy=True, language=language),
        )
    else:
        await message.answer(
            success_template.format(proxy=valid_proxy),
            reply_markup=proxy_menu(has_proxy=True, language=language),
        )


@router.callback_query(F.data.startswith("language:"))
async def choose_language(
    callback: CallbackQuery,
    bot: Bot,
    settings: Settings,
    session_factory: sessionmaker[Session],
) -> None:
    if not isinstance(callback.message, Message):
        return
    parts = (callback.data or "").split(":")
    if len(parts) == 2 and parts[1] == "start":
        await callback.answer()
        await callback.message.edit_text(LANGUAGE_PROMPT, reply_markup=language_menu())
        return
    if len(parts) == 3 and parts[1] == "start":
        language = parts[2]
        if language not in LANGUAGES:
            invalid_msg = INVALID_LANGUAGE_MESSAGES.get("en", "Invalid language.")
            await callback.answer(invalid_msg, show_alert=True)
            return
        with session_factory() as session:
            set_user_language(
                session, callback.from_user.id, callback.from_user.username, language
            )
        locale = get_locale(language)
        await callback.answer()
        if not await has_access(bot, callback.from_user.id, settings):
            channel_names = "\n".join(
                f"📢 {channel}" for channel in settings.required_channel_list
            )
            text = locale.join_required
            if channel_names:
                text = f"{text}\n\n{channel_names}"
            await callback.message.edit_text(
                text,
                reply_markup=membership_menu(settings.required_channel_list, language),
            )
            return
        await callback.message.edit_text(
            f"{locale.welcome}\n\n{locale.choose_option}",
            reply_markup=main_menu(language),
        )
        return

    language = parts[1] if len(parts) == 2 else ""
    if language not in LANGUAGES:
        invalid_msg = INVALID_LANGUAGE_MESSAGES.get("en", "Invalid language.")
        await callback.answer(invalid_msg, show_alert=True)
        return
    await callback.answer()
    await callback.message.edit_text(
        LANGUAGE_PROMPTS[language],
        reply_markup=language_menu(language),
    )


@router.callback_query(F.data.startswith("membership:check:"))
async def check_membership(
    callback: CallbackQuery,
    bot: Bot,
    settings: Settings,
    session_factory: sessionmaker[Session],
) -> None:
    if not isinstance(callback.message, Message):
        return
    requested_language = (callback.data or "").rsplit(":", 1)[-1]
    with session_factory() as session:
        stored_language = get_user_language(session, callback.from_user.id)
    language = (
        requested_language if requested_language in LANGUAGES else stored_language
    )
    locale = get_locale(language)
    missing = await missing_memberships(
        bot, callback.from_user.id, settings.required_channel_list
    )
    if missing:
        await callback.answer(locale.membership_incomplete, show_alert=True)
        return
    await callback.answer(locale.membership_verified)
    await callback.message.edit_text(
        f"✅ {locale.membership_verified}\n\n"
        f"{locale.welcome}\n\n{locale.choose_option}",
        reply_markup=main_menu(language),
    )


@router.callback_query(F.data == "menu:language")
async def change_language(callback: CallbackQuery) -> None:
    await callback.answer()
    if isinstance(callback.message, Message):
        await callback.message.edit_text(LANGUAGE_PROMPT, reply_markup=language_menu())


@router.callback_query(F.data == "section:noop")
async def section_header(
    callback: CallbackQuery, session_factory: sessionmaker[Session]
) -> None:
    language = user_language(session_factory, callback.from_user.id)
    await callback.answer(action_message(language, 0))


@router.callback_query(F.data == "feature:planned")
async def planned_feature(
    callback: CallbackQuery, session_factory: sessionmaker[Session]
) -> None:
    language = user_language(session_factory, callback.from_user.id)
    await callback.answer(action_message(language, 1), show_alert=True)


@router.callback_query(F.data == "feature:restricted")
async def restricted_feature(
    callback: CallbackQuery, session_factory: sessionmaker[Session]
) -> None:
    language = user_language(session_factory, callback.from_user.id)
    await callback.answer(action_message(language, 2), show_alert=True)


@router.callback_query(F.data == "action:cancel")
async def callback_cancel(
    callback: CallbackQuery,
    state: FSMContext,
    session_factory: sessionmaker[Session],
) -> None:
    await clear_state_and_file(state)
    language = user_language(session_factory, callback.from_user.id)
    await callback.answer(action_message(language, 3))
    if isinstance(callback.message, Message):
        await callback.message.edit_text(
            action_message(language, 3), reply_markup=main_menu(language)
        )


@router.callback_query(F.data == "menu:help")
async def help_menu(
    callback: CallbackQuery,
    state: FSMContext,
    settings: Settings,
    session_factory: sessionmaker[Session],
) -> None:
    await clear_state_and_file(state)
    await callback.answer()
    if isinstance(callback.message, Message):
        language = user_language(session_factory, callback.from_user.id)
        contact = resolve_support_contact(settings.support_id)
        if contact is None:
            msg = SUPPORT_UNAVAILABLE.get(language, SUPPORT_UNAVAILABLE["en"])
        else:
            template = HELP_MESSAGES.get(language, HELP_MESSAGES["en"])
            msg = template.format(support_id=html.quote(contact[0]))
        await callback.message.edit_text(
            msg,
            reply_markup=help_support_menu(settings.support_id, language),
        )


@router.callback_query(F.data == "menu:back")
async def back_to_main_menu(
    callback: CallbackQuery,
    state: FSMContext,
    session_factory: sessionmaker[Session],
) -> None:
    await clear_state_and_file(state)
    await callback.answer()
    if isinstance(callback.message, Message):
        language = user_language(session_factory, callback.from_user.id)
        locale = get_locale(language)
        await callback.message.edit_text(
            f"{locale.welcome}\n\n{locale.choose_option}",
            reply_markup=main_menu(language),
        )


@router.callback_query(F.data == "menu:privacy")
async def privacy_menu(
    callback: CallbackQuery, session_factory: sessionmaker[Session]
) -> None:
    await callback.answer()
    if isinstance(callback.message, Message):
        language = user_language(session_factory, callback.from_user.id)
        msg = PRIVACY_MESSAGES.get(language, PRIVACY_MESSAGES["en"])
        await callback.message.edit_text(msg, reply_markup=main_menu(language))


@router.callback_query(F.data == "menu:account_age")
async def account_age_menu(
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


@router.callback_query(F.data == "menu:plan")
async def plan_menu(
    callback: CallbackQuery,
    settings: Settings,
    session_factory: sessionmaker[Session],
) -> None:
    await callback.answer()
    if isinstance(callback.message, Message):
        language = user_language(session_factory, callback.from_user.id)
        template = PLAN_MESSAGES.get(language, PLAN_MESSAGES["en"])
        msg = template.format(max_mb=settings.max_upload_mb)
        await callback.message.edit_text(msg, reply_markup=main_menu(language))
