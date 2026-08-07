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
    PaymentWalletAction,
    VIPNav,
    VIPPlanAction,
)
from app.admin.keyboards import (
    build_admin_cancel_keyboard,
    build_feature_gates_keyboard,
    build_payment_hub_keyboard,
    build_vip_menu_keyboard,
    build_vip_plans_keyboard,
)
from app.admin.states import AddVIPPlanState, PaymentSettingState
from app.db.repositories import (
    activate_vip_subscription_flow,
    add_vip_plan,
    delete_vip_plan,
    get_payment_settings,
    get_vip_plan,
    list_feature_gates,
    list_pending_payments,
    list_vip_plans,
    reject_payment,
    toggle_feature_access_level,
    update_payment_settings,
)
from app.services.addresses import (
    is_valid_bep20_address,
    is_valid_binance_id,
    is_valid_trc20_address,
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


@router.callback_query(VIPPlanAction.filter(F.action == "view"))
async def callback_view_plan(query: CallbackQuery, callback_data: VIPPlanAction, session: Session) -> None:
    """Show details of a single VIP plan."""
    plan = get_vip_plan(session, callback_data.plan_id)
    if plan is None:
        await query.answer("❌ Plan not found.", show_alert=True)
        return
    text = (
        "📦 <b>VIP Plan Details</b>\n\n"
        f"🆔 <b>ID:</b> <code>{plan.id}</code>\n"
        f"🏷️ <b>Name:</b> <code>{html.escape(plan.name)}</code>\n"
        f"🗓️ <b>Duration:</b> <code>{plan.months} month(s)</code>\n"
        f"💵 <b>Price:</b> <code>${plan.price:.2f} {html.escape(plan.currency)}</code>\n"
        f"✅ <b>Active:</b> <code>{'Yes' if plan.is_active else 'No'}</code>\n"
        f"🕒 <b>Created:</b> <code>{plan.created_at.strftime('%Y-%m-%d %H:%M')}</code>"
    )
    if isinstance(query.message, Message):
        with contextlib.suppress(TelegramBadRequest):
            await query.message.edit_text(
                text,
                reply_markup=build_admin_cancel_keyboard("vip"),
                parse_mode="HTML",
            )
    await query.answer()


@router.callback_query(VIPPlanAction.filter(F.action == "delete"))
async def callback_delete_plan(query: CallbackQuery, callback_data: VIPPlanAction, session: Session) -> None:
    """Delete specified VIP plan."""
    from sqlalchemy.exc import IntegrityError

    try:
        deleted = delete_vip_plan(session, callback_data.plan_id)
    except IntegrityError:
        await query.answer(
            "🚫 Cannot delete: plan has payment history.",
            show_alert=True,
        )
        return
    if not deleted:
        await query.answer("❌ Plan not found.", show_alert=True)
        return
    await query.answer("🗑️ Plan deleted.", show_alert=True)
    plans = list_vip_plans(session, active_only=True)
    if isinstance(query.message, Message):
        with contextlib.suppress(TelegramBadRequest):
            await query.message.edit_reply_markup(reply_markup=build_vip_plans_keyboard(plans))


WALLET_FIELD_LABELS = {
    "binance_id": "Binance UID",
    "trc20_address": "Manual TRC20",
    "bep20_address": "Manual BEP20",
    "auto_trc20_address": "Auto TRC20",
    "auto_bep20_address": "Auto BEP20",
}

WALLET_FIELD_VALIDATORS = {
    "binance_id": is_valid_binance_id,
    "trc20_address": is_valid_trc20_address,
    "bep20_address": is_valid_bep20_address,
    "auto_trc20_address": is_valid_trc20_address,
    "auto_bep20_address": is_valid_bep20_address,
}

WALLET_FIELD_EXAMPLES = {
    "binance_id": "e.g. 12456789",
    "trc20_address": "T-prefixed base58 address, e.g. TYjo5oG4t7b2j13j1dqjtYBgGJ6faxTYZW",
    "bep20_address": "0x + 40 hex chars",
    "auto_trc20_address": "T-prefixed base58 address (auto-order payout)",
    "auto_bep20_address": "0x + 40 hex chars (auto-order payout)",
}


def _payment_hub_text(ps, pending_list: list) -> str:
    """Format the Payment Hub message body for the given settings and pending orders."""
    lines = [
        "💳 <b>Payment Gateway & Verification Hub</b>\n",
        "<b>Manual Payment:</b> <code>{}</code>      <b>Auto Payment:</b> <code>{}</code>\n".format(
            "ON" if ps.manual_enabled else "OFF",
            "ON" if ps.auto_enabled else "OFF",
        ),
        "<b>Binance UID:</b> <code>{}</code>",
        "<b>Manual TRC20:</b> <code>{}</code>",
        "<b>Manual BEP20:</b> <code>{}</code>",
        "<b>Auto TRC20:</b> <code>{}</code>",
        "<b>Auto BEP20:</b> <code>{}</code>\n",
        "⏳ <b>Pending Verification Orders:</b> <code>{}</code>",
    ]
    text = "\n".join(lines).format(
        html.escape(ps.binance_id or "Not Set"),
        html.escape(ps.trc20_address or "Not Set"),
        html.escape(ps.bep20_address or "Not Set"),
        html.escape(ps.auto_trc20_address or "Not Set"),
        html.escape(ps.auto_bep20_address or "Not Set"),
        len(pending_list),
    )

    for p in pending_list[:5]:
        text += (
            f"\n• Payment #{p.id} — User #{p.user_id} (${p.amount} {p.currency})\n"
            f"  Method: <code>{html.escape(p.payment_method)}</code> | TX: <code>{html.escape(p.transaction_id or 'N/A')}</code>"
        )

    if ps.auto_enabled and not (ps.auto_trc20_address and ps.auto_bep20_address):
        text += "\n\n⚠️ <b>Auto Payment is ON but a wallet is missing</b> — auto orders are blocked until both Auto TRC20 and Auto BEP20 are set."
    if ps.updated_at:
        text += f"\n\n🕓 <i>Last updated: {html.escape(ps.updated_at.strftime('%Y-%m-%d %H:%M UTC'))}</i>"
    return text


async def _send_payment_hub(chat: Message, session: Session) -> None:
    """Post the Payment Hub as a fresh message (used after wizard input)."""
    ps = get_payment_settings(session)
    pending_list = list_pending_payments(session)
    reply_kb = build_payment_hub_keyboard(ps, pending_list)
    await chat.answer(_payment_hub_text(ps, pending_list), reply_markup=reply_kb, parse_mode="HTML")


async def _render_payment_hub(query: CallbackQuery, session: Session, state: FSMContext, clear_field: str = "") -> None:
    """Render the Payment Gateway & Verification Hub view (stateless, button-driven)."""
    await state.clear()
    ps = get_payment_settings(session)
    pending_list = list_pending_payments(session)
    text = _payment_hub_text(ps, pending_list)
    reply_kb = build_payment_hub_keyboard(ps, pending_list, clear_field=clear_field)
    if isinstance(query.message, Message):
        with contextlib.suppress(TelegramBadRequest):
            await query.message.edit_text(text, reply_markup=reply_kb, parse_mode="HTML")
    await query.answer()


@router.callback_query(VIPNav.filter(F.section == "payments"))
async def callback_payment_settings(query: CallbackQuery, session: Session, state: FSMContext) -> None:
    """Render Payment Settings & Pending Manual Approval orders with Inline Action buttons."""
    await _render_payment_hub(query, session, state)


@router.callback_query(PaymentWalletAction.filter(F.action == "edit"))
async def callback_edit_wallet(
    query: CallbackQuery, callback_data: PaymentWalletAction, state: FSMContext
) -> None:
    """Start the wallet-value wizard: collect a replacement value for one field."""
    field = callback_data.field
    label = WALLET_FIELD_LABELS.get(field, field)
    await state.set_state(PaymentSettingState.waiting_for_wallet_value)
    await state.update_data(wallet_field=field)
    text = (
        "✏️ <b>Edit Wallet</b>\n\n"
        f"Enter the new <b>{label}</b> value below:\n"
        f"<code>{WALLET_FIELD_EXAMPLES.get(field, '')}</code>\n\n"
        "Send the value in one message, or press Cancel."
    )
    if isinstance(query.message, Message):
        with contextlib.suppress(TelegramBadRequest):
            await query.message.edit_text(
                text,
                reply_markup=build_admin_cancel_keyboard("vip"),
                parse_mode="HTML",
            )
    await query.answer()


@router.callback_query(PaymentWalletAction.filter(F.action == "clear"))
async def callback_clear_wallet_confirm(
    query: CallbackQuery, callback_data: PaymentWalletAction, session: Session, state: FSMContext
) -> None:
    """Show inline confirmation before removing a wallet value."""
    await _render_payment_hub(query, session, state, clear_field=callback_data.field)


@router.callback_query(PaymentWalletAction.filter(F.action == "clear_cancel"))
async def callback_clear_wallet_cancel(
    query: CallbackQuery, callback_data: PaymentWalletAction, session: Session, state: FSMContext
) -> None:
    """Keep the wallet when the admin backs out of the clear confirmation."""
    await _render_payment_hub(query, session, state)


@router.callback_query(PaymentWalletAction.filter(F.action == "clear_confirm"))
async def callback_clear_wallet_do(
    query: CallbackQuery, callback_data: PaymentWalletAction, session: Session, state: FSMContext
) -> None:
    """Remove the confirmed wallet value."""
    field = callback_data.field
    label = WALLET_FIELD_LABELS.get(field, field)
    update_payment_settings(session, **{field: None})
    await query.answer(f"🗑️ {label} cleared.", show_alert=True)
    await _render_payment_hub(query, session, state)


@router.message(PaymentSettingState.waiting_for_wallet_value)
async def process_wallet_value_input(message: Message, state: FSMContext, session: Session) -> None:
    """Validate and persist a single wallet value collected by the edit wizard."""
    data = await state.get_data()
    field = data.get("wallet_field", "")
    label = WALLET_FIELD_LABELS.get(field, "Wallet")
    validator = WALLET_FIELD_VALIDATORS.get(field)

    if field not in WALLET_FIELD_VALIDATORS:
        await state.clear()
        return

    raw = (message.text or "").strip()
    if not raw:
        await message.reply(
            f"❌ Empty value — nothing saved. Send a value for <b>{label}</b> or press Cancel.",
            reply_markup=build_admin_cancel_keyboard("vip"),
            parse_mode="HTML",
        )
        return

    if not validator(raw):
        hint = WALLET_FIELD_EXAMPLES.get(field, "")
        await message.reply(
            f"❌ <b>Invalid {label}</b>. {hint}.\n\n"
            "Nothing was saved — send a corrected value or press Cancel.",
            reply_markup=build_admin_cancel_keyboard("vip"),
            parse_mode="HTML",
        )
        return

    update_payment_settings(session, **{field: raw})
    await state.clear()
    await message.reply(f"✅ <b>{label}</b> updated successfully!")
    await _send_payment_hub(message, session)


@router.callback_query(PaymentAction.filter())
async def callback_payment_action(
    query: CallbackQuery, callback_data: PaymentAction, session: Session, state: FSMContext
) -> None:
    """Approve, Reject or toggle payment gateways directly via Inline Buttons."""
    payment_id = callback_data.payment_id
    action = callback_data.action
    await state.clear()

    if action == "toggle_manual":
        ps = get_payment_settings(session)
        update_payment_settings(session, manual_enabled=not ps.manual_enabled)
        await query.answer(f"Manual Payment: {'ON' if not ps.manual_enabled else 'OFF'}", show_alert=True)
    elif action == "toggle_auto":
        ps = get_payment_settings(session)
        update_payment_settings(session, auto_enabled=not ps.auto_enabled)
        await query.answer(f"Auto Payment: {'ON' if not ps.auto_enabled else 'OFF'}", show_alert=True)
    elif action == "approve":
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
    await _render_payment_hub(query, session, state)


@router.message(F.text.startswith("/approve_pay_"))
async def command_approve_payment(
    message: Message, session: Session, admin_role: str
) -> None:
    """Approve manual payment order (legacy text command fallback)."""
    from app.admin.rbac import has_permission

    if not has_permission(admin_role, "ADMIN"):
        await message.reply("🚫 Payment management requires ADMIN role or higher.")
        return
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
async def command_reject_payment(
    message: Message, session: Session, admin_role: str
) -> None:
    """Reject manual payment order (legacy text command fallback)."""
    from app.admin.rbac import has_permission

    if not has_permission(admin_role, "ADMIN"):
        await message.reply("🚫 Payment management requires ADMIN role or higher.")
        return
    try:
        payment_id = int((message.text or "").replace("/reject_pay_", "").strip())
        ok = reject_payment(session, payment_id)
        if ok:
            await message.reply(f"🚫 Payment #{payment_id} REJECTED.")
        else:
            await message.reply("❌ Payment not found or already processed.")
    except ValueError:
        await message.reply("Invalid Payment ID format.")
