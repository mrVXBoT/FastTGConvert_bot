import logging

from aiogram import F, Router, html
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.types import CallbackQuery, Message
from sqlalchemy.orm import Session, sessionmaker

from app.config import Settings
from app.db.repositories import (
    create_payment_order,
    get_payment_settings,
    get_user_by_telegram_id,
    get_user_language,
    get_vip_plan,
    list_vip_plans,
    upsert_user,
)
from app.keyboards import user_vip_plans_menu, vip_checkout_menu
from app.locales import (
    VIP_CENTER_MESSAGES,
    VIP_CHECKOUT_MESSAGES,
    VIP_PAYMENT_SUBMITTED_MESSAGES,
    VIP_STATUS_LABELS,
)

LOGGER = logging.getLogger(__name__)
router = Router(name="user_vip")


class UserVIPState(StatesGroup):
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
    """Render payment gateway details for chosen VIP plan."""
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
    await state.set_state(UserVIPState.waiting_for_receipt)

    checkout_template = VIP_CHECKOUT_MESSAGES.get(language, VIP_CHECKOUT_MESSAGES["en"])
    text = checkout_template.format(
        name=html.quote(plan.name),
        price=plan.price,
        currency=plan.currency,
        months=plan.months,
        trc20=html.quote(ps.trc20_address or "Contact Support"),
        bep20=html.quote(ps.bep20_address or "Contact Support"),
        binance=html.quote(ps.binance_id or "Contact Support"),
    )

    if isinstance(query.message, Message):
        await query.message.edit_text(text, reply_markup=vip_checkout_menu(language), parse_mode="HTML")
    await query.answer()


@router.message(UserVIPState.waiting_for_receipt)
async def process_user_receipt_submission(
    message: Message,
    state: FSMContext,
    settings: Settings,
    session_factory: sessionmaker[Session] | None = None,
    session: Session | None = None,
) -> None:
    """Receive user receipt / TX hash and create pending Payment order for admin review."""
    data = await state.get_data()
    plan_id = data.get("plan_id")
    amount = data.get("amount", 10.0)
    await state.clear()

    tg_user = message.from_user
    if not tg_user or not plan_id:
        return

    def _create_order(sess: Session):
        u = upsert_user(sess, tg_user.id, tg_user.username)
        tx_text = message.text or message.caption or "Receipt Photo"
        receipt_file_id = message.photo[-1].file_id if message.photo else None
        p = create_payment_order(
            sess,
            user_id=u.id,
            plan_id=plan_id,
            amount=amount,
            payment_method="manual",
            transaction_id=tx_text if message.text else None,
            receipt_file_id=receipt_file_id,
        )
        return u, p, tx_text

    if session is not None:
        user, payment, tx_text = _create_order(session)
        language = get_user_language(session, tg_user.id)
    elif session_factory is not None:
        with session_factory() as sess:
            user, payment, tx_text = _create_order(sess)
            language = get_user_language(sess, tg_user.id)
    else:
        from app.db.session import get_default_session_factory

        df_sf = get_default_session_factory()
        if df_sf is None:
            return
        with df_sf() as sess:
            user, payment, tx_text = _create_order(sess)
            language = get_user_language(sess, tg_user.id)

    submitted_template = VIP_PAYMENT_SUBMITTED_MESSAGES.get(language, VIP_PAYMENT_SUBMITTED_MESSAGES["en"])
    await message.reply(
        submitted_template.format(id=payment.id),
        parse_mode="HTML",
    )

    # Notify System Owner / Admin
    owner_id = settings.admin_id
    if owner_id and message.bot:
        try:
            admin_msg = (
                f"🔔 <b>New VIP Payment Order #{payment.id}</b>\n\n"
                f"👤 User: <code>{user.telegram_id}</code> (@{html.quote(user.username or 'N/A')})\n"
                f"💰 Amount: <code>${payment.amount} {payment.currency}</code>\n"
                f"📄 TX Info: <code>{html.quote(tx_text)}</code>\n\n"
                f"👉 Approve: /approve_pay_{payment.id}\n"
                f"👉 Reject: /reject_pay_{payment.id}"
            )
            await message.bot.send_message(chat_id=owner_id, text=admin_msg, parse_mode="HTML")
        except Exception as exc:  # noqa: BLE001
            LOGGER.debug("Failed to send payment approval message to admin: %s", exc)
