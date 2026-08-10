import logging
import shutil
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
    PRIVACY_MESSAGES,
    PROXY_FAIL_MESSAGES,
    PROXY_INVALID_MESSAGES,
    PROXY_MESSAGES,
    PROXY_REMOVED_MESSAGES,
    PROXY_SUCCESS_MESSAGES,
    PROXY_TESTING_MESSAGES,
    REFERRAL_MESSAGES,
    REFERRAL_NEXT_TIER_LABELS,
    REFERRAL_NOTIFY_MESSAGES,
    REFERRAL_REWARD_LABELS,
    REFERRAL_TIER_LABELS,
    SUPPORT_UNAVAILABLE,
    action_message,
    get_locale,
    proxy_status_text,
)
from app.services.force_join import (
    get_active_force_join_channels,
    get_force_join_invite_links,
)
from app.services.membership import missing_memberships
from app.states import AccountAge, ProxyState

router = Router(name="start")
LOGGER = logging.getLogger(__name__)


async def clear_state_and_file(state: FSMContext) -> None:
    data = await state.get_data()
    for key in ("source_path", "temp_file_path", "file_path"):
        stored_path = data.get(key)
        if stored_path:
            Path(stored_path).unlink(missing_ok=True)
    temp_dir = data.get("temp_dir")
    if temp_dir:
        shutil.rmtree(Path(temp_dir), ignore_errors=True)
    otp_sessions = data.get("otp_sessions", [])
    for sess in otp_sessions:
        sp = sess.get("session_path")
        if sp:
            Path(sp).unlink(missing_ok=True)
    otp_work_dir = data.get("otp_work_dir")
    if otp_work_dir:
        shutil.rmtree(Path(otp_work_dir), ignore_errors=True)
    two_factor_batch_dir = data.get("two_factor_batch_dir")
    if two_factor_batch_dir:
        shutil.rmtree(Path(two_factor_batch_dir), ignore_errors=True)
    for stored in data.get("two_factor_session_files", []):
        Path(str(stored)).unlink(missing_ok=True)
    await state.clear()


async def has_access(
    bot: Bot, user_id: int, settings: Settings, session_factory: sessionmaker[Session]
) -> bool:
    with session_factory() as session:
        channels = get_active_force_join_channels(session, settings)
    return not await missing_memberships(bot, user_id, tuple(channels))


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

    await process_referral_payload(message, bot, session_factory)

    if language not in LANGUAGES:
        await message.answer(LANGUAGE_PROMPT, reply_markup=language_menu())
        return
    locale = get_locale(language)
    with session_factory() as session:
        required_channels = get_active_force_join_channels(session, settings)
        invite_links = get_force_join_invite_links(session)
    if not await has_access(bot, message.from_user.id, settings, session_factory):
        channel_names = "\n".join(f"📢 {channel}" for channel in required_channels)
        text = locale.join_required
        if channel_names:
            text = f"{text}\n\n{channel_names}"
        await message.answer(
            text,
            reply_markup=membership_menu(tuple(required_channels), language, invite_links),
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


async def process_referral_payload(
    message: Message, bot: Bot, session_factory: sessionmaker[Session]
) -> None:
    """Handle /start ref_<id> payloads: register the referral and notify the referrer."""
    if message.from_user is None:
        return
    args = (message.text or "").split(maxsplit=1)
    payload = args[1] if len(args) > 1 else ""
    if not payload.startswith("ref_"):
        return
    try:
        referrer_id = int(payload[4:])
    except ValueError:
        return
    if referrer_id == message.from_user.id:
        return

    from app.db.repositories import (
        get_user_language,
        register_referral,
    )

    outcome: dict = {}
    with session_factory() as session:
        outcome = register_referral(session, referrer_id, message.from_user.id)

    if not outcome.get("ok"):
        return
    try:
        with session_factory() as session:
            referrer_lang = get_user_language(session, referrer_id)
        notify_template = REFERRAL_NOTIFY_MESSAGES.get(
            referrer_lang, REFERRAL_NOTIFY_MESSAGES["en"]
        )
        reward_text = ""
        if outcome.get("granted_days"):
            reward_label = REFERRAL_REWARD_LABELS.get(
                referrer_lang, REFERRAL_REWARD_LABELS["en"]
            )
            reward_text = reward_label.format(days=outcome["granted_days"])
        notify_text = notify_template.format(
            count=outcome.get("referred_count", 0), reward=reward_text
        )
        from app.ui import EmojiRegistry

        await bot.send_message(
            referrer_id, EmojiRegistry.enrich(notify_text), disable_web_page_preview=True
        )
    except Exception:  # noqa: BLE001
        LOGGER.debug("Referrer notification skipped: %s", referrer_id)


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
        from app.db.repositories import (
            get_referral_stats,
            list_referral_tiers,
        )

        stats = get_referral_stats(session, message.from_user.id)
        tiers = list_referral_tiers(session, active_only=True)
    bot_info = await bot.get_me()
    bot_username = bot_info.username or "FastTGConvert_bot"
    ref_link = f"https://t.me/{bot_username}?start=ref_{message.from_user.id}"

    tier_lines = []
    for tier in tiers:
        tier_lines.append(
            REFERRAL_TIER_LABELS.get(language, REFERRAL_TIER_LABELS["en"]).format(
                refs=tier.refs_required, days=tier.reward_days
            )
        )
    tiers_text = "\n".join(tier_lines)
    if tiers_text:
        tiers_text += "\n"

    next_line = ""
    next_tier = stats.get("next_tier")
    if next_tier:
        next_line = (
            REFERRAL_NEXT_TIER_LABELS.get(
                language, REFERRAL_NEXT_TIER_LABELS["en"]
            ).format(
                refs=next_tier["refs"],
                days=next_tier["days"],
                remaining=next_tier["refs"] - stats["referred"],
            )
            + "\n"
        )

    template = REFERRAL_MESSAGES.get(language, REFERRAL_MESSAGES["en"])
    msg = template.format(
        ref_link=ref_link,
        user_id=message.from_user.id,
        referred=stats["referred"],
        earned_days=stats["earned_days"],
        next_tier=next_line,
        tiers=tiers_text,
    )
    from app.ui import EmojiRegistry

    await message.answer(EmojiRegistry.enrich(msg), disable_web_page_preview=True)


def validate_proxy_url(proxy_str: str) -> str | None:
    from app.services.proxy import normalize_proxy_string

    return normalize_proxy_string(proxy_str)



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
    user_str = f"{callback.from_user.full_name} (@{callback.from_user.username or callback.from_user.id})"
    LOGGER.info("User %s removed custom proxy", user_str)
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

    raw_text = (message.text or "").strip()
    if message.document:
        try:
            bot = message.bot
            if bot:
                downloaded = await bot.download(message.document)
                if hasattr(downloaded, "read"):
                    raw_text = downloaded.read().decode("utf-8", errors="ignore")
                elif isinstance(downloaded, bytes):
                    raw_text = downloaded.decode("utf-8", errors="ignore")
        except Exception as exc:  # noqa: BLE001
            LOGGER.warning("Failed to read uploaded proxy file: %s", exc)

    from app.services.proxy import (
        parse_proxy_pool,
        parse_telethon_proxy,
        test_proxy_connection,
    )

    pool = parse_proxy_pool(raw_text)
    user_str = f"{message.from_user.full_name} (@{message.from_user.username or message.from_user.id})"

    if not pool:
        LOGGER.warning("User %s entered invalid proxy format: %s", user_str, raw_text[:50])
        msg = PROXY_INVALID_MESSAGES.get(language, PROXY_INVALID_MESSAGES["en"])
        await message.answer(msg, reply_markup=cancel_menu(language))
        return

    sample_proxy = pool[0]
    testing_template = PROXY_TESTING_MESSAGES.get(
        language, PROXY_TESTING_MESSAGES["en"]
    )
    testing_msg = await message.answer(testing_template)

    parsed_tuple = parse_telethon_proxy(sample_proxy)
    is_ok, detail = await test_proxy_connection(parsed_tuple, timeout=5.0)

    if not is_ok:
        LOGGER.warning("Proxy test failed for user %s (%s): %s", user_str, detail, sample_proxy)
        fail_template = PROXY_FAIL_MESSAGES.get(
            language, PROXY_FAIL_MESSAGES["en"]
        )
        fail_msg = fail_template.format(detail=detail)
        if isinstance(testing_msg, Message):
            await testing_msg.edit_text(fail_msg, reply_markup=cancel_menu(language))
        else:
            await message.answer(fail_msg, reply_markup=cancel_menu(language))
        return

    proxy_to_save = "\n".join(pool) if len(pool) > 1 else pool[0]
    with session_factory() as session:
        set_user_proxy(session, message.from_user.id, proxy_to_save)
    await state.clear()

    if len(pool) > 1:
        LOGGER.info("User %s saved Proxy Pool of %d proxies", user_str, len(pool))
        msg_text = (
            f"✅ Multi-Proxy Pool Activated!\n"
            f"Total proxies: {len(pool)}\n"
            f"Requests will be rotated across all proxies automatically (Round-Robin)."
        )
    else:
        LOGGER.info("User %s set custom proxy: %s", user_str, pool[0])
        success_template = PROXY_SUCCESS_MESSAGES.get(
            language, PROXY_SUCCESS_MESSAGES["en"]
        )
        msg_text = success_template.format(proxy=pool[0])

    if isinstance(testing_msg, Message):
        await testing_msg.edit_text(
            msg_text,
            reply_markup=proxy_menu(has_proxy=True, language=language),
        )
    else:
        await message.answer(
            msg_text,
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
        language = language if language in LANGUAGES else ""
    else:
        language = parts[1] if len(parts) == 2 else ""
    if language not in LANGUAGES:
        invalid_msg = INVALID_LANGUAGE_MESSAGES.get("en", "Invalid language.")
        await callback.answer(invalid_msg, show_alert=True)
        return
    with session_factory() as session:
        set_user_language(
            session, callback.from_user.id, callback.from_user.username, language
        )
    locale = get_locale(language)
    await callback.answer(locale.language_name)
    with session_factory() as session:
        required_channels = get_active_force_join_channels(session, settings)
        invite_links = get_force_join_invite_links(session)
    if not await has_access(bot, callback.from_user.id, settings, session_factory):
        channel_names = "\n".join(f"📢 {channel}" for channel in required_channels)
        text = locale.join_required
        if channel_names:
            text = f"{text}\n\n{channel_names}"
        await callback.message.edit_text(
            text,
            reply_markup=membership_menu(tuple(required_channels), language, invite_links),
        )
        return
    await callback.message.edit_text(
        f"{locale.welcome}\n\n{locale.choose_option}",
        reply_markup=main_menu(language),
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
    with session_factory() as session:
        required_channels = get_active_force_join_channels(session, settings)
    missing = await missing_memberships(
        bot, callback.from_user.id, tuple(required_channels)
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
async def change_language(
    callback: CallbackQuery, session_factory: sessionmaker[Session]
) -> None:
    await callback.answer()
    if isinstance(callback.message, Message):
        language = user_language(session_factory, callback.from_user.id)
        prompt = LANGUAGE_PROMPTS.get(language, LANGUAGE_PROMPT)
        await callback.message.edit_text(
            prompt, reply_markup=language_menu(language)
        )


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


@router.callback_query(F.data == "flow:cancel")
async def callback_flow_cancel(
    callback: CallbackQuery,
    state: FSMContext,
    session_factory: sessionmaker[Session],
) -> None:
    """Generic flow cancel (Profile Setup account menu) — same as action:cancel."""
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
    session_factory: sessionmaker[Session],
) -> None:
    await callback.answer()
    if isinstance(callback.message, Message):
        with session_factory() as session:
            from app.db.repositories import get_user_by_telegram_id, list_vip_plans
            from app.keyboards import user_vip_plans_menu

            user = callback.from_user
            plans = list_vip_plans(session, active_only=True)
            user_db = get_user_by_telegram_id(session, user.id) if user else None
            language = user_language(session_factory, user.id) if user else "en"

            from app.locales import VIP_CENTER_MESSAGES, VIP_STATUS_LABELS

            status_labels = VIP_STATUS_LABELS.get(language, VIP_STATUS_LABELS["en"])
            vip_status_str = status_labels["vip"] if (user_db and user_db.is_vip) else status_labels["free"]
            center_template = VIP_CENTER_MESSAGES.get(language, VIP_CENTER_MESSAGES["en"])
            text = center_template.format(status=vip_status_str)
            await callback.message.edit_text(
                text,
                reply_markup=user_vip_plans_menu(plans, language=language),
                parse_mode="HTML",
            )
