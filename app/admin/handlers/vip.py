"""app/admin/handlers/vip.py — 💎 VIP Management, Dynamic Feature Gate, Plans & Payment Verification router."""

from __future__ import annotations

import contextlib
import html

from aiogram import F, Router
from aiogram.exceptions import TelegramBadRequest
from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery, Message
from sqlalchemy.orm import Session

from app.admin.callbacks import (
    AdminNav,
    FeatureToggle,
    PaymentAction,
    VIPNav,
    VIPPlanAction,
)
from app.admin.keyboards import (
    build_admin_cancel_keyboard,
    build_feature_gates_keyboard,
    build_pending_payments_keyboard,
    build_vip_menu_keyboard,
    build_vip_plans_keyboard,
)
from app.admin.states import AddVIPPlanState, PaymentSettingState
from app.db.repositories import (
    activate_vip_subscription_flow,
    add_vip_plan,
    delete_vip_plan,
    get_payment_settings,
    list_feature_gates,
    list_pending_payments,
    list_vip_plans,
    reject_payment,
    toggle_feature_access_level,
    update_payment_settings,
)

router = Router()


@router.callback_query(AdminNav.filter(F.action == "vip"))
async def callback_vip_main_menu(query: CallbackQuery, state: FSMContext) -> None:
    """Render VIP Management main menu and clear active FSM state."""
    await state.clear()
    text = (
        "💎 <b>VIP Management & Feature Control Hub</b>\n\n"
        "Configure dynamic feature access levels, pricing plans, and payment gateways below:"
    )
    if isinstance(query.message, Message):
        with contextlib.suppress(TelegramBadRequest):
            await query.message.edit_text(text, reply_markup=build_vip_menu_keyboard(), parse_mode="HTML")
    await query.answer()


@router.callback_query(VIPNav.filter(F.section == "features"))
async def callback_feature_gates(query: CallbackQuery, session: Session) -> None:
    """Render Feature Gates level toggling keyboard."""
    features = list_feature_gates(session)
    text = (
        "⚙️ <b>Dynamic Feature Access Control</b>\n\n"
        "Click on any feature button to toggle access level between <b>FREE FOR ALL</b> and <b>VIP ONLY</b>:"
    )
    if isinstance(query.message, Message):
        with contextlib.suppress(TelegramBadRequest):
            await query.message.edit_text(text, reply_markup=build_feature_gates_keyboard(features), parse_mode="HTML")
    await query.answer()


@router.callback_query(FeatureToggle.filter())
async def callback_toggle_feature(query: CallbackQuery, callback_data: FeatureToggle, session: Session) -> None:
    """Toggle access level for a specific feature."""
    updated = toggle_feature_access_level(session, callback_data.feature_key)
    if updated:
        await query.answer(f"Updated {updated.title} to {updated.access_level}!", show_alert=True)
    features = list_feature_gates(session)
    if isinstance(query.message, Message):
        with contextlib.suppress(TelegramBadRequest):
            await query.message.edit_reply_markup(reply_markup=build_feature_gates_keyboard(features))


@router.callback_query(VIPNav.filter(F.section == "plans"))
async def callback_vip_plans(query: CallbackQuery, session: Session) -> None:
    """Render VIP Plans list."""
    plans = list_vip_plans(session, active_only=True)
    text = (
        "📦 <b>VIP Plans Management</b>\n\n"
        "Manage active subscription packages available to users:"
    )
    if isinstance(query.message, Message):
        with contextlib.suppress(TelegramBadRequest):
            await query.message.edit_text(text, reply_markup=build_vip_plans_keyboard(plans), parse_mode="HTML")
    await query.answer()


@router.callback_query(VIPPlanAction.filter(F.action == "add"))
async def callback_add_plan_start(query: CallbackQuery, state: FSMContext) -> None:
    """Prompt for new VIP plan format."""
    await state.set_state(AddVIPPlanState.waiting_for_plan_details)
    text = (
        "➕ <b>Add New VIP Plan</b>\n\n"
        "Please send plan details in format:\n"
        "<code>Name | Months | PriceUSD</code>\n\n"
        "Example: <code>3 Months VIP | 3 | 25.0</code>"
    )
    if isinstance(query.message, Message):
        with contextlib.suppress(TelegramBadRequest):
            await query.message.edit_text(
                text,
                reply_markup=build_admin_cancel_keyboard("vip"),
                parse_mode="HTML",
            )
    await query.answer()


@router.message(AddVIPPlanState.waiting_for_plan_details)
async def process_add_plan_input(message: Message, state: FSMContext, session: Session) -> None:
    """Parse and add new VIP plan."""
    await state.clear()
    raw = (message.text or "").split("|")
    if len(raw) != 3:
        await message.reply(
            "❌ Invalid format. Expected <code>Name | Months | Price</code>",
            reply_markup=build_admin_cancel_keyboard("vip"),
            parse_mode="HTML",
        )
        return
    try:
        name = raw[0].strip()
        months = int(raw[1].strip())
        price = float(raw[2].strip())
        add_vip_plan(session, name=name, months=months, price=price)
        await message.reply(
            f"✅ VIP Plan <code>{html.escape(name)}</code> added successfully!",
            reply_markup=build_admin_cancel_keyboard("vip"),
            parse_mode="HTML",
        )
    except ValueError:
        await message.reply(
            "❌ Invalid numeric values for months or price.",
            reply_markup=build_admin_cancel_keyboard("vip"),
        )


@router.callback_query(VIPPlanAction.filter(F.action == "delete"))
async def callback_delete_plan(query: CallbackQuery, callback_data: VIPPlanAction, session: Session) -> None:
    """Delete specified VIP plan."""
    delete_vip_plan(session, callback_data.plan_id)
    await query.answer("🗑️ Plan deleted.", show_alert=True)
    plans = list_vip_plans(session, active_only=True)
    if isinstance(query.message, Message):
        with contextlib.suppress(TelegramBadRequest):
            await query.message.edit_reply_markup(reply_markup=build_vip_plans_keyboard(plans))


@router.callback_query(VIPNav.filter(F.section == "payments"))
async def callback_payment_settings(query: CallbackQuery, session: Session, state: FSMContext) -> None:
    """Render Payment Settings & Pending Manual Approval orders with Inline Action buttons."""
    await state.set_state(PaymentSettingState.waiting_for_wallets)
    ps = get_payment_settings(session)
    pending_list = list_pending_payments(session)

    lines = [
        "💳 <b>Payment Gateway & Verification Hub</b>\n",
        f"<b>Manual Payment:</b> <code>{'ON' if ps.manual_enabled else 'OFF'}</code>\n",
        f"<b>Binance ID:</b> <code>{html.escape(ps.binance_id or 'Not Set')}</code>\n",
        f"<b>TRC20 Address:</b> <code>{html.escape(ps.trc20_address or 'Not Set')}</code>\n",
        f"<b>BEP20 Address:</b> <code>{html.escape(ps.bep20_address or 'Not Set')}</code>\n",
        f"⏳ <b>Pending Verification Orders:</b> <code>{len(pending_list)}</code>\n",
    ]

    for p in pending_list[:5]:
        lines.append(
            f"• Payment #{p.id} — User #{p.user_id} (${p.amount} {p.currency})\n"
            f"  Method: <code>{html.escape(p.payment_method)}</code> | TX: <code>{html.escape(p.transaction_id or 'N/A')}</code>"
        )

    lines.append("\nTo update wallet addresses, send text in format:\n<code>BinanceID | TRC20Address | BEP20Address</code>")

    reply_kb = build_pending_payments_keyboard(pending_list[:5])
    if isinstance(query.message, Message):
        with contextlib.suppress(TelegramBadRequest):
            await query.message.edit_text("\n".join(lines), reply_markup=reply_kb, parse_mode="HTML")
    await query.answer()


@router.callback_query(PaymentAction.filter())
async def callback_payment_action(query: CallbackQuery, callback_data: PaymentAction, session: Session) -> None:
    """Approve or Reject manual payment orders directly via Inline Buttons."""
    payment_id = callback_data.payment_id
    action = callback_data.action

    if action == "approve":
        sub = activate_vip_subscription_flow(session, payment_id)
        if sub:
            await query.answer(f"✅ Payment #{payment_id} APPROVED! VIP active until {sub.expires_at.strftime('%Y-%m-%d')}.", show_alert=True)
        else:
            await query.answer("❌ Payment not found or already processed.", show_alert=True)
    elif action == "reject":
        ok = reject_payment(session, payment_id)
        if ok:
            await query.answer(f"🚫 Payment #{payment_id} REJECTED.", show_alert=True)
        else:
            await query.answer("❌ Payment not found or already processed.", show_alert=True)

    # Refresh payment settings view
    ps = get_payment_settings(session)
    pending_list = list_pending_payments(session)

    lines = [
        "💳 <b>Payment Gateway & Verification Hub</b>\n",
        f"<b>Manual Payment:</b> <code>{'ON' if ps.manual_enabled else 'OFF'}</code>\n",
        f"<b>Binance ID:</b> <code>{html.escape(ps.binance_id or 'Not Set')}</code>\n",
        f"<b>TRC20 Address:</b> <code>{html.escape(ps.trc20_address or 'Not Set')}</code>\n",
        f"<b>BEP20 Address:</b> <code>{html.escape(ps.bep20_address or 'Not Set')}</code>\n",
        f"⏳ <b>Pending Verification Orders:</b> <code>{len(pending_list)}</code>\n",
    ]

    for p in pending_list[:5]:
        lines.append(
            f"• Payment #{p.id} — User #{p.user_id} (${p.amount} {p.currency})\n"
            f"  Method: <code>{html.escape(p.payment_method)}</code> | TX: <code>{html.escape(p.transaction_id or 'N/A')}</code>"
        )

    lines.append("\nTo update wallet addresses, send text in format:\n<code>BinanceID | TRC20Address | BEP20Address</code>")

    reply_kb = build_pending_payments_keyboard(pending_list[:5])
    if isinstance(query.message, Message):
        with contextlib.suppress(TelegramBadRequest):
            await query.message.edit_text("\n".join(lines), reply_markup=reply_kb, parse_mode="HTML")


@router.message(F.text.startswith("/approve_pay_"))
async def command_approve_payment(message: Message, session: Session) -> None:
    """Approve manual payment order (legacy text command fallback)."""
    try:
        payment_id = int((message.text or "").replace("/approve_pay_", "").strip())
        sub = activate_vip_subscription_flow(session, payment_id)
        if sub:
            await message.reply(f"✅ Payment #{payment_id} APPROVED! VIP Subscription #{sub.id} created until {sub.expires_at.strftime('%Y-%m-%d')}.")
        else:
            await message.reply("❌ Payment not found or already processed.")
    except ValueError:
        await message.reply("Invalid Payment ID format.")


@router.message(F.text.startswith("/reject_pay_"))
async def command_reject_payment(message: Message, session: Session) -> None:
    """Reject manual payment order (legacy text command fallback)."""
    try:
        payment_id = int((message.text or "").replace("/reject_pay_", "").strip())
        ok = reject_payment(session, payment_id)
        if ok:
            await message.reply(f"🚫 Payment #{payment_id} REJECTED.")
        else:
            await message.reply("❌ Payment not found or already processed.")
    except ValueError:
        await message.reply("Invalid Payment ID format.")


@router.message(PaymentSettingState.waiting_for_wallets)
async def process_payment_wallets_input(message: Message, state: FSMContext, session: Session) -> None:
    """Update wallet configuration addresses."""
    await state.clear()
    parts = (message.text or "").split("|")
    binance = parts[0].strip() if len(parts) > 0 else None
    trc20 = parts[1].strip() if len(parts) > 1 else None
    bep20 = parts[2].strip() if len(parts) > 2 else None

    update_payment_settings(session, binance_id=binance, trc20_address=trc20, bep20_address=bep20)
    await message.reply(
        "✅ Payment wallet addresses updated successfully!",
        reply_markup=build_admin_cancel_keyboard("vip"),
        parse_mode="HTML",
    )
