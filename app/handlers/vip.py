"""app/handlers/vip.py — User-facing VIP Purchase Flow, Payment Request & Receipt submission."""

from __future__ import annotations

import logging

from aiogram import F, Router
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.types import CallbackQuery, Message
from sqlalchemy.orm import Session

from app.config import Settings
from app.db.repositories import (
    create_payment_order,
    get_payment_settings,
    get_user_by_telegram_id,
    get_vip_plan,
    list_vip_plans,
    upsert_user,
)
from app.keyboards import user_vip_plans_menu

LOGGER = logging.getLogger(__name__)
router = Router(name="user_vip")


class UserVIPState(StatesGroup):
    waiting_for_receipt = State()


@router.message(Command("vip"))
@router.message(F.text == "💎 VIP")
async def command_user_vip(message: Message, session: Session) -> None:
    """Render user VIP subscription menu with pricing plans."""
    plans = list_vip_plans(session, active_only=True)
    if message.from_user:
        upsert_user(session, message.from_user.id, message.from_user.username)

    user_db = get_user_by_telegram_id(session, message.from_user.id) if message.from_user else None
    vip_status_str = "💎 **Active VIP Member**" if (user_db and user_db.is_vip) else "⚪ **Free Plan**"

    text = (
        f"💎 **VIP Subscription Center**\n\n"
        f"Current Status: {vip_status_str}\n\n"
        "**VIP Benefits:**\n"
        "• Unlimited Fast File Conversions\n"
        "• High Priority Server Queue\n"
        "• Advanced Telethon Features\n\n"
        "Select a subscription plan below to upgrade:"
    )

    await message.answer(text, reply_markup=user_vip_plans_menu(plans), parse_mode="Markdown")


@router.callback_query(F.data.startswith("buy_plan:"))
async def callback_buy_plan(query: CallbackQuery, session: Session, state: FSMContext) -> None:
    """Render payment gateway details for chosen VIP plan."""
    if not query.data:
        return

    try:
        plan_id = int(query.data.split(":")[1])
    except (ValueError, IndexError):
        await query.answer("Invalid plan selected.")
        return

    plan = get_vip_plan(session, plan_id)
    if not plan:
        await query.answer("Plan no longer active.")
        return

    ps = get_payment_settings(session)
    await state.update_data(plan_id=plan.id, amount=plan.price)
    await state.set_state(UserVIPState.waiting_for_receipt)

    text = (
        f"💳 **Checkout — {plan.name}**\n\n"
        f"**Amount:** `{plan.price} {plan.currency}`\n"
        f"**Duration:** `{plan.months} Month(s)`\n\n"
        "**Available Payment Methods:**\n"
        f"• **TRC20 USDT:** `{ps.trc20_address or 'Contact Support'}`\n"
        f"• **BEP20 USDT:** `{ps.bep20_address or 'Contact Support'}`\n"
        f"• **Binance Pay ID:** `{ps.binance_id or 'Contact Support'}`\n\n"
        "📥 **Next Step:** Transfer exact amount to any address above, then send your **Transaction Hash / Photo Receipt** here:"
    )

    if isinstance(query.message, Message):
        await query.message.edit_text(text, parse_mode="Markdown")
    await query.answer()


@router.message(UserVIPState.waiting_for_receipt)
async def process_user_receipt_submission(
    message: Message, state: FSMContext, session: Session, settings: Settings
) -> None:
    """Receive user receipt / TX hash and create pending Payment order for admin review."""
    data = await state.get_data()
    plan_id = data.get("plan_id")
    amount = data.get("amount", 10.0)
    await state.clear()

    if not message.from_user or not plan_id:
        return

    user = upsert_user(session, message.from_user.id, message.from_user.username)
    tx_text = message.text or message.caption or "Receipt Photo"
    receipt_file_id = message.photo[-1].file_id if message.photo else None

    # Create Pending Payment Record
    payment = create_payment_order(
        session,
        user_id=user.id,
        plan_id=plan_id,
        amount=amount,
        payment_method="manual",
        transaction_id=tx_text if message.text else None,
        receipt_file_id=receipt_file_id,
    )

    await message.reply(
        f"✅ **Payment Order #{payment.id} Submitted!**\n\n"
        "Our administrative team is reviewing your transaction. You will be notified immediately upon approval.",
        parse_mode="Markdown",
    )

    # Notify System Owner / Admin
    owner_id = settings.admin_id
    if owner_id and message.bot:
        try:
            admin_msg = (
                f"🔔 **New VIP Payment Order #{payment.id}**\n\n"
                f"👤 User: `{user.telegram_id}` (@{user.username or 'N/A'})\n"
                f"💰 Amount: `${payment.amount} {payment.currency}`\n"
                f"📄 TX Info: `{tx_text}`\n\n"
                f"👉 Approve: /approve_pay_{payment.id}\n"
                f"👉 Reject: /reject_pay_{payment.id}"
            )
            await message.bot.send_message(chat_id=owner_id, text=admin_msg, parse_mode="Markdown")
        except Exception as exc:  # noqa: BLE001
            LOGGER.debug("Failed to send payment approval message to admin: %s", exc)
