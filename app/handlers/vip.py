import logging
from datetime import datetime, timedelta, timezone

UTC = timezone.utc  # noqa: UP017  (py<3.11 compat)

from aiogram import F, Router, html
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.types import CallbackQuery, InlineKeyboardMarkup, Message
from sqlalchemy.orm import Session, sessionmaker

from app.config import Settings
from app.db.repositories import (
    create_auto_payment_orders,
    create_payment_order,
    get_activated_subscription_since,
    get_active_subscription,
    get_payment_settings,
    get_user_by_telegram_id,
    get_user_language,
    get_vip_plan,
    list_vip_plans,
    upsert_user,
)
from app.keyboards import (
    _premium_icon_button,
    auto_payment_control_menu,
    main_menu,
    manual_payment_done_menu,
    user_vip_plans_menu,
    vip_payment_method_menu,
)
from app.locales import (
    AUTO_PAYMENT_CHAIN_MESSAGES,
    AUTO_PAYMENT_HEADER_MESSAGES,
    CANCEL_LABELS,
    MANUAL_PAYMENT_MESSAGES,
    PAYMENT_CONFIRMED_MESSAGES,
    PAYMENT_FLOW_LABELS,
    PAYMENT_METHOD_UNAVAILABLE_MESSAGES,
    PAYMENT_NOT_DETECTED_MESSAGES,
    RECEIPT_INVALID_MESSAGES,
    RECEIPT_PROMPT_MESSAGES,
    VIP_CENTER_MESSAGES,
    VIP_PAYMENT_METHOD_MESSAGES,
    VIP_PAYMENT_SUBMITTED_MESSAGES,
    VIP_STATUS_LABELS,
)
from app.services.payments import check_pending_auto_payments, generate_expected_amount
from app.ui import ButtonStyle

LOGGER = logging.getLogger(__name__)
router = Router(name="user_vip")


class UserVIPState(StatesGroup):
    waiting_payment_method = State()
    waiting_for_receipt = State()


@router.message(Command("vip"))
@router.message(F.text == "💎 VIP")
@router.callback_query(F.data == "menu:plan")
@router.callback_query(F.data == "menu:vip")
async def command_user_vip(
    event: Message | CallbackQuery,
    session_factory: sessionmaker[Session] | None = None,
    session: Session | None = None,
) -> None:
    """Render user VIP subscription menu with pricing plans."""
    user = event.from_user
    if not user:
        return

    if session is not None:
        plans = list_vip_plans(session, active_only=True)
        upsert_user(session, user.id, user.username)
        user_db = get_user_by_telegram_id(session, user.id)
        language = get_user_language(session, user.id)
    elif session_factory is not None:
        with session_factory() as sess:
            plans = list_vip_plans(sess, active_only=True)
            upsert_user(sess, user.id, user.username)
            user_db = get_user_by_telegram_id(sess, user.id)
            language = get_user_language(sess, user.id)
    else:
        from app.db.session import get_default_session_factory

        df_sf = get_default_session_factory()
        if df_sf is None:
            return
        with df_sf() as sess:
            plans = list_vip_plans(sess, active_only=True)
            upsert_user(sess, user.id, user.username)
            user_db = get_user_by_telegram_id(sess, user.id)
            language = get_user_language(sess, user.id)

    status_labels = VIP_STATUS_LABELS.get(language, VIP_STATUS_LABELS["en"])
    vip_status_str = status_labels["vip"] if (user_db and user_db.is_vip) else status_labels["free"]
    center_template = VIP_CENTER_MESSAGES.get(language, VIP_CENTER_MESSAGES["en"])
    text = center_template.format(status=vip_status_str)

    if isinstance(event, CallbackQuery):
        await event.answer()
        if isinstance(event.message, Message):
            await event.message.edit_text(
                text, reply_markup=user_vip_plans_menu(plans, language=language), parse_mode="HTML"
            )
    else:
        await event.answer(text, reply_markup=user_vip_plans_menu(plans, language=language), parse_mode="HTML")


@router.callback_query(F.data.startswith("buy_plan:"))
async def callback_buy_plan(
    query: CallbackQuery,
    state: FSMContext,
    session_factory: sessionmaker[Session] | None = None,
    session: Session | None = None,
) -> None:
    """Render payment method choice screen for the selected VIP plan."""
    if not query.data:
        return

    try:
        plan_id = int(query.data.split(":")[1])
    except (ValueError, IndexError):
        await query.answer("Invalid plan selected.")
        return

    def _get_details(sess: Session):
        p = get_vip_plan(sess, plan_id)
        ps = get_payment_settings(sess) if p else None
        return p, ps

    if session is not None:
        plan, ps = _get_details(session)
        language = get_user_language(session, query.from_user.id)
    elif session_factory is not None:
        with session_factory() as sess:
            plan, ps = _get_details(sess)
            language = get_user_language(sess, query.from_user.id)
    else:
        from app.db.session import get_default_session_factory

        df_sf = get_default_session_factory()
        if df_sf is None:
            return
        with df_sf() as sess:
            plan, ps = _get_details(sess)
            language = get_user_language(sess, query.from_user.id)

    if not plan or not ps:
        await query.answer("Plan no longer active.")
        return

    await state.update_data(plan_id=plan.id, amount=plan.price)
    await state.set_state(UserVIPState.waiting_payment_method)

    method_template = VIP_PAYMENT_METHOD_MESSAGES.get(
        language, VIP_PAYMENT_METHOD_MESSAGES["en"]
    )
    text = method_template.format(
        name=html.quote(plan.name),
        price=plan.price,
        currency=plan.currency,
    )

    manual_enabled = bool(
        ps.manual_enabled and (ps.trc20_address or ps.bep20_address or ps.binance_id)
    )
    auto_enabled = bool(
        ps.auto_enabled and ps.auto_trc20_address and ps.auto_bep20_address
    )

    if isinstance(query.message, Message):
        await query.message.edit_text(
            text,
            reply_markup=vip_payment_method_menu(language, manual_enabled, auto_enabled),
            parse_mode="HTML",
        )
    await query.answer()


@router.callback_query(F.data == "pay_method:manual")
async def callback_manual_payment(
    query: CallbackQuery,
    state: FSMContext,
    session_factory: sessionmaker[Session] | None = None,
    session: Session | None = None,
) -> None:
    """Show manual payment wallets and ask for a receipt screenshot."""
    data = await state.get_data()
    plan_id = data.get("plan_id")
    if not plan_id:
        await query.answer()
        return

    def _get_details(sess: Session):
        p = get_vip_plan(sess, plan_id)
        ps = get_payment_settings(sess) if p else None
        return p, ps

    if session is not None:
        plan, ps = _get_details(session)
        language = get_user_language(session, query.from_user.id)
    elif session_factory is not None:
        with session_factory() as sess:
            plan, ps = _get_details(sess)
            language = get_user_language(sess, query.from_user.id)
    else:
        from app.db.session import get_default_session_factory

        df_sf = get_default_session_factory()
        if df_sf is None:
            return
        with df_sf() as sess:
            plan, ps = _get_details(sess)
            language = get_user_language(sess, query.from_user.id)

    if not plan or not ps:
        await query.answer()
        return

    if not ps.manual_enabled:
        unavailable_template = PAYMENT_METHOD_UNAVAILABLE_MESSAGES.get(
            language, PAYMENT_METHOD_UNAVAILABLE_MESSAGES["en"]
        )
        await query.answer(unavailable_template, show_alert=True)
        return

    await state.update_data(plan_id=plan.id, amount=plan.price)
    await state.set_state(UserVIPState.waiting_for_receipt)

    manual_template = MANUAL_PAYMENT_MESSAGES.get(
        language, MANUAL_PAYMENT_MESSAGES["en"]
    )
    text = manual_template.format(
        name=html.quote(plan.name),
        price=plan.price,
        currency=plan.currency,
        binance=html.quote(ps.binance_id or "Contact Support"),
        trc20=html.quote(ps.trc20_address or "Contact Support"),
        bep20=html.quote(ps.bep20_address or "Contact Support"),
    )

    if isinstance(query.message, Message):
        await query.message.edit_text(
            text, reply_markup=manual_payment_done_menu(language), parse_mode="HTML"
        )
    await query.answer()


@router.callback_query(F.data == "pay:manual_screenshot")
async def callback_manual_screenshot(
    query: CallbackQuery,
    state: FSMContext,
    session_factory: sessionmaker[Session] | None = None,
    session: Session | None = None,
) -> None:
    """Prompt the user to upload their receipt screenshot (photo only)."""
    data = await state.get_data()
    plan_id = data.get("plan_id")
    if not plan_id:
        await query.answer()
        return

    def _get_plan(sess: Session):
        return get_vip_plan(sess, plan_id)

    if session is not None:
        plan = _get_plan(session)
        language = get_user_language(session, query.from_user.id)
    elif session_factory is not None:
        with session_factory() as sess:
            plan = _get_plan(sess)
            language = get_user_language(sess, query.from_user.id)
    else:
        from app.db.session import get_default_session_factory

        df_sf = get_default_session_factory()
        if df_sf is None:
            return
        with df_sf() as sess:
            plan = _get_plan(sess)
            language = get_user_language(sess, query.from_user.id)

    if not plan:
        await query.answer()
        return

    prompt_template = RECEIPT_PROMPT_MESSAGES.get(
        language, RECEIPT_PROMPT_MESSAGES["en"]
    )
    text = prompt_template.format(name=html.quote(plan.name))

    cancel_lbl = CANCEL_LABELS.get(language, CANCEL_LABELS["en"])
    cancel_markup = InlineKeyboardMarkup(
        inline_keyboard=[
            [
                _premium_icon_button(
                    cancel_lbl, "action:cancel", "CANCEL", style=ButtonStyle.DANGER
                )
            ]
        ]
    )

    if isinstance(query.message, Message):
        await query.message.edit_text(
            text, reply_markup=cancel_markup, parse_mode="HTML"
        )
    await query.answer()


@router.message(UserVIPState.waiting_for_receipt)
async def process_user_receipt_submission(
    message: Message,
    state: FSMContext,
    settings: Settings,
    session_factory: sessionmaker[Session] | None = None,
    session: Session | None = None,
) -> None:
    """Receive a receipt screenshot and create a pending manual Payment order."""
    tg_user = message.from_user
    if not tg_user:
        return

    def _get_language(sess: Session) -> str:
        return get_user_language(sess, tg_user.id)

    if session is not None:
        language = _get_language(session)
    elif session_factory is not None:
        with session_factory() as sess:
            language = _get_language(sess)
    else:
        from app.db.session import get_default_session_factory

        df_sf = get_default_session_factory()
        if df_sf is None:
            return
        with df_sf() as sess:
            language = _get_language(sess)

    if not message.photo:
        invalid_template = RECEIPT_INVALID_MESSAGES.get(
            language, RECEIPT_INVALID_MESSAGES["en"]
        )
        await message.reply(invalid_template, parse_mode="HTML")
        return

    receipt_file_id = message.photo[-1].file_id
    data = await state.get_data()
    plan_id = data.get("plan_id")
    amount = data.get("amount", 10.0)
    if not plan_id:
        return

    def _create_order(sess: Session):
        u = upsert_user(sess, tg_user.id, tg_user.username)
        p = create_payment_order(
            sess,
            user_id=u.id,
            plan_id=plan_id,
            amount=amount,
            payment_method="manual",
            transaction_id=None,
            receipt_file_id=receipt_file_id,
        )
        return u, p

    if session is not None:
        user, payment = _create_order(session)
        language = get_user_language(session, tg_user.id)
    elif session_factory is not None:
        with session_factory() as sess:
            user, payment = _create_order(sess)
            language = get_user_language(sess, tg_user.id)
    else:
        from app.db.session import get_default_session_factory

        df_sf = get_default_session_factory()
        if df_sf is None:
            return
        with df_sf() as sess:
            user, payment = _create_order(sess)
            language = get_user_language(sess, tg_user.id)

    await state.clear()

    submitted_template = VIP_PAYMENT_SUBMITTED_MESSAGES.get(
        language, VIP_PAYMENT_SUBMITTED_MESSAGES["en"]
    )
    await message.reply(submitted_template.format(id=payment.id), parse_mode="HTML")

    # Notify System Owner / Admin
    owner_id = settings.admin_id
    if owner_id and message.bot:
        try:
            admin_msg = (
                f"🔔 <b>New VIP Payment Order #{payment.id}</b>\n\n"
                f"👤 User: <code>{user.telegram_id}</code> (@{html.quote(user.username or 'N/A')})\n"
                f"💰 Amount: <code>${payment.amount} {payment.currency}</code>\n"
                f"📄 TX Info: <code>Manual Screenshot Receipt</code>\n\n"
                f"👉 Approve: /approve_pay_{payment.id}\n"
                f"👉 Reject: /reject_pay_{payment.id}"
            )
            await message.bot.send_message(chat_id=owner_id, text=admin_msg, parse_mode="HTML")
        except Exception as exc:  # noqa: BLE001
            LOGGER.debug("Failed to send payment approval message to admin: %s", exc)


@router.callback_query(F.data == "pay_method:auto")
async def callback_auto_payment(
    query: CallbackQuery,
    state: FSMContext,
    settings: Settings,
    session_factory: sessionmaker[Session] | None = None,
    session: Session | None = None,
) -> None:
    """Create auto crypto payment orders (TRC20 + BEP20) and render instructions."""
    data = await state.get_data()
    plan_id = data.get("plan_id")
    if not plan_id:
        await query.answer()
        return

    def _get_details(sess: Session):
        p = get_vip_plan(sess, plan_id)
        ps = get_payment_settings(sess) if p else None
        return p, ps

    if session is not None:
        plan, ps = _get_details(session)
        language = get_user_language(session, query.from_user.id)
    elif session_factory is not None:
        with session_factory() as sess:
            plan, ps = _get_details(sess)
            language = get_user_language(sess, query.from_user.id)
    else:
        from app.db.session import get_default_session_factory

        df_sf = get_default_session_factory()
        if df_sf is None:
            return
        with df_sf() as sess:
            plan, ps = _get_details(sess)
            language = get_user_language(sess, query.from_user.id)

    if not plan or not ps:
        await query.answer()
        return

    if not (ps.auto_enabled and ps.auto_trc20_address and ps.auto_bep20_address):
        unavailable_template = PAYMENT_METHOD_UNAVAILABLE_MESSAGES.get(
            language, PAYMENT_METHOD_UNAVAILABLE_MESSAGES["en"]
        )
        await query.answer(unavailable_template, show_alert=True)
        return

    used: set[float] = set()
    trc20_amt = generate_expected_amount(plan.price, used)
    used.add(trc20_amt)
    bep20_amt = generate_expected_amount(plan.price, used)

    def _create_orders(sess: Session):
        u = upsert_user(sess, query.from_user.id, query.from_user.username)
        return create_auto_payment_orders(
            sess,
            u.id,
            plan.id,
            plan.price,
            plan.currency,
            trc20_wallet=ps.auto_trc20_address,
            bep20_wallet=ps.auto_bep20_address,
            trc20_amount=trc20_amt,
            bep20_amount=bep20_amt,
            order_hours=settings.payment_order_hours,
        )

    try:
        if session is not None:
            orders = _create_orders(session)
        elif session_factory is not None:
            with session_factory() as sess:
                orders = _create_orders(sess)
        else:
            from app.db.session import get_default_session_factory

            df_sf = get_default_session_factory()
            if df_sf is None:
                return
            with df_sf() as sess:
                orders = _create_orders(sess)
    except RuntimeError:
        # Retry-exhaustion inside create_auto_payment_orders: impossible to create a
        # unique order right now; let the user try again instead of swallowing it and
        # silently showing instructions that are no longer valid.
        LOGGER.exception(
            "Could not create auto payment orders for user %s", query.from_user.id
        )
        retry_template = PAYMENT_METHOD_UNAVAILABLE_MESSAGES.get(
            language, PAYMENT_METHOD_UNAVAILABLE_MESSAGES["en"]
        )
        if isinstance(query.message, Message):
            await query.message.edit_text(
                retry_template,
                reply_markup=auto_payment_control_menu(language),
                parse_mode="HTML",
            )
        await query.answer()
        return

    labels = PAYMENT_FLOW_LABELS.get(language, PAYMENT_FLOW_LABELS["en"])
    chain_template = AUTO_PAYMENT_CHAIN_MESSAGES.get(
        language, AUTO_PAYMENT_CHAIN_MESSAGES["en"]
    )
    trc20_block = chain_template.format(
        chain=labels["chain_trc20"],
        wallet=html.quote(ps.auto_trc20_address),
        amount=f"{trc20_amt:.3f}",
        order=orders[0].order_code,
        hours=settings.payment_order_hours,
    )
    bep20_block = chain_template.format(
        chain=labels["chain_bep20"],
        wallet=html.quote(ps.auto_bep20_address),
        amount=f"{bep20_amt:.3f}",
        order=orders[1].order_code,
        hours=settings.payment_order_hours,
    )
    chains_block = (
        trc20_block + "\n─────────────────────\n" + bep20_block + "\n"
    )

    header_template = AUTO_PAYMENT_HEADER_MESSAGES.get(
        language, AUTO_PAYMENT_HEADER_MESSAGES["en"]
    )
    text = header_template.format(
        name=html.quote(plan.name),
        price=plan.price,
        currency=plan.currency,
        chains=chains_block,
    )

    await state.set_state(UserVIPState.waiting_payment_method)

    if isinstance(query.message, Message):
        await query.message.edit_text(
            text, reply_markup=auto_payment_control_menu(language), parse_mode="HTML"
        )
    await query.answer()


@router.callback_query(F.data == "pay:auto_check")
async def callback_auto_check(
    query: CallbackQuery,
    state: FSMContext,
    settings: Settings,
    session_factory: sessionmaker[Session] | None = None,
    session: Session | None = None,
) -> None:
    """Scan pending auto payments for the user and confirm VIP if paid."""
    await query.answer()

    sf = session_factory
    if sf is None:
        from app.db.session import get_default_session_factory

        sf = get_default_session_factory()
    if sf is None:
        return

    with sf() as sess:
        language = get_user_language(sess, query.from_user.id)

    result = await check_pending_auto_payments(
        sf, query.bot, settings, only_user_id=query.from_user.id
    )

    if result["paid"] > 0:
        await state.clear()
        plan_name = "VIP"
        expiry_str = datetime.now(UTC).strftime("%Y-%m-%d")
        with sf() as sess:
            active_sub = get_active_subscription(sess, query.from_user.id)
            if active_sub:
                plan_obj = get_vip_plan(sess, active_sub.plan_id)
                if plan_obj:
                    plan_name = plan_obj.name
                expiry_str = active_sub.expires_at.strftime("%Y-%m-%d")
        confirmed_template = PAYMENT_CONFIRMED_MESSAGES.get(
            language, PAYMENT_CONFIRMED_MESSAGES["en"]
        )
        text = confirmed_template.format(plan=plan_name, date=expiry_str)
        if isinstance(query.message, Message):
            await query.message.edit_text(
                text, reply_markup=main_menu(language), parse_mode="HTML"
            )
    else:
        # M2 guard: if the payment loop already activated this user (e.g. the poll
        # swept the order before they pressed the button), the pending scan finds
        # nothing — but the user DID pay. Show the confirmation instead of a
        # misleading "payment not detected".
        activated = False
        since = datetime.now(UTC) - timedelta(
            hours=settings.payment_order_hours + 2
        )
        with sf() as sess:
            late_sub = get_activated_subscription_since(
                sess, query.from_user.id, since
            )
            if late_sub is not None:
                activated = True
                plan_name = "VIP"
                plan_obj = get_vip_plan(sess, late_sub.plan_id)
                if plan_obj:
                    plan_name = plan_obj.name
                late_expiry = late_sub.expires_at.strftime("%Y-%m-%d")
        if activated:
            await state.clear()
            confirmed_template = PAYMENT_CONFIRMED_MESSAGES.get(
                language, PAYMENT_CONFIRMED_MESSAGES["en"]
            )
            text = confirmed_template.format(plan=plan_name, date=late_expiry)
            if isinstance(query.message, Message):
                await query.message.edit_text(
                    text, reply_markup=main_menu(language), parse_mode="HTML"
                )
        else:
            not_detected_template = PAYMENT_NOT_DETECTED_MESSAGES.get(
                language, PAYMENT_NOT_DETECTED_MESSAGES["en"]
            )
            await query.answer(not_detected_template, show_alert=True)


