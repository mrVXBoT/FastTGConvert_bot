"""app/admin/handlers/referral.py — 🔗 Referral System management: reward tiers,
referral records & granted rewards with pagination."""

from __future__ import annotations

import contextlib
import html
import math

from aiogram import F, Router
from aiogram.exceptions import TelegramBadRequest
from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery, Message
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.admin.callbacks import AdminNav, ReferralNav, ReferralTierAction
from app.admin.keyboards import (
    build_admin_cancel_keyboard,
    build_referral_list_nav_keyboard,
    build_referral_menu_keyboard,
    build_referral_tiers_keyboard,
)
from app.admin.states import AddReferralTierState
from app.db.models import ReferralReward
from app.db.repositories import (
    add_referral_tier,
    delete_referral_tier,
    get_user_by_telegram_id,
    is_referral_enabled,
    list_referral_rewards_paginated,
    list_referral_tiers,
    list_referrals_paginated,
    set_referral_enabled,
    toggle_referral_tier,
)

router = Router()

_PAGE_SIZE = 8


def _render_referral_menu_text(session: Session) -> str:
    """Build the Referral System main menu text with current totals."""
    enabled = is_referral_enabled(session)
    tiers = list_referral_tiers(session)
    _, total_referrals = list_referrals_paginated(session, page=1, page_size=1)
    all_rewards = list(session.scalars(select(ReferralReward)).all())
    total_rewards = sum(r.days for r in all_rewards)
    return (
        "🔗 <b>Referral System Management</b>\n\n"
        f"🟢 <b>Status:</b> <code>{'ENABLED' if enabled else 'DISABLED'}</code>\n"
        f"👥 <b>Total Referrals:</b> <code>{total_referrals}</code>\n"
        f"🎁 <b>Total VIP Days Granted:</b> <code>{total_rewards}</code>\n"
        f"🏆 <b>Active Tiers:</b> <code>{sum(1 for t in tiers if t.is_active)}/{len(tiers)}</code>"
    )


async def _render_referral_menu(query: CallbackQuery, session: Session) -> None:
    if isinstance(query.message, Message):
        with contextlib.suppress(TelegramBadRequest):
            await query.message.edit_text(
                _render_referral_menu_text(session),
                reply_markup=build_referral_menu_keyboard(),
                parse_mode="HTML",
            )
    await query.answer()


@router.callback_query(AdminNav.filter(F.action == "referral"))
async def callback_referral_main_menu(query: CallbackQuery, state: FSMContext, session: Session) -> None:
    """Render Referral System main submenu."""
    await state.clear()
    await _render_referral_menu(query, session)


@router.callback_query(ReferralNav.filter(F.section == "menu"))
async def callback_referral_menu_section(query: CallbackQuery, session: Session) -> None:
    """Re-render Referral System main submenu (from sub-sections)."""
    await _render_referral_menu(query, session)


@router.callback_query(ReferralNav.filter(F.section == "tiers"))
async def callback_referral_tiers(query: CallbackQuery, session: Session) -> None:
    """Render reward tiers management list."""
    tiers = list_referral_tiers(session)
    text = (
        "🏆 <b>Referral Reward Tiers</b>\n\n"
        "Each tier unlocks when the referrer reaches the required number of referrals.\n"
        "Click a tier to toggle it, or Delete to remove it:"
    )
    if isinstance(query.message, Message):
        with contextlib.suppress(TelegramBadRequest):
            await query.message.edit_text(text, reply_markup=build_referral_tiers_keyboard(tiers), parse_mode="HTML")
    await query.answer()


@router.callback_query(ReferralTierAction.filter(F.action == "toggle"))
async def callback_referral_tier_toggle(
    query: CallbackQuery, callback_data: ReferralTierAction, session: Session
) -> None:
    """Toggle a reward tier on/off."""
    tier = toggle_referral_tier(session, callback_data.tier_id)
    if tier:
        await query.answer(
            f"Tier {tier.refs_required} refs → {tier.reward_days} days: {'ON' if tier.is_active else 'OFF'}",
            show_alert=True,
        )
    tiers = list_referral_tiers(session)
    if isinstance(query.message, Message):
        with contextlib.suppress(TelegramBadRequest):
            await query.message.edit_reply_markup(reply_markup=build_referral_tiers_keyboard(tiers))


@router.callback_query(ReferralTierAction.filter(F.action == "delete"))
async def callback_referral_tier_delete(
    query: CallbackQuery, callback_data: ReferralTierAction, session: Session
) -> None:
    """Delete a reward tier."""
    deleted = delete_referral_tier(session, callback_data.tier_id)
    await query.answer("🗑️ Tier deleted." if deleted else "❌ Tier not found.", show_alert=True)
    tiers = list_referral_tiers(session)
    if isinstance(query.message, Message):
        with contextlib.suppress(TelegramBadRequest):
            await query.message.edit_reply_markup(reply_markup=build_referral_tiers_keyboard(tiers))


@router.callback_query(F.data == "adm_ref_tier_add")
async def callback_referral_tier_add_start(query: CallbackQuery, state: FSMContext) -> None:
    """Prompt for new reward tier input."""
    await state.set_state(AddReferralTierState.waiting_for_tier_details)
    text = (
        "➕ <b>Add New Referral Tier</b>\n\n"
        "Please send tier details in format:\n"
        "<code>RefsRequired | RewardDays</code>\n\n"
        "Example: <code>10 | 10</code>  (10 referrals → 10 days VIP)"
    )
    if isinstance(query.message, Message):
        with contextlib.suppress(TelegramBadRequest):
            await query.message.edit_text(text, reply_markup=build_admin_cancel_keyboard("referral"), parse_mode="HTML")
    await query.answer()


@router.message(AddReferralTierState.waiting_for_tier_details)
async def process_referral_tier_input(message: Message, state: FSMContext, session: Session) -> None:
    """Parse and add a new referral reward tier."""
    await state.clear()
    raw = (message.text or "").split("|")
    if len(raw) != 2:
        await message.reply(
            "❌ Invalid format. Expected <code>RefsRequired | RewardDays</code>",
            reply_markup=build_admin_cancel_keyboard("referral"),
            parse_mode="HTML",
        )
        return
    try:
        refs_required = int(raw[0].strip())
        reward_days = int(raw[1].strip())
    except ValueError:
        await message.reply(
            "❌ Invalid numeric values. Expected <code>RefsRequired | RewardDays</code>",
            reply_markup=build_admin_cancel_keyboard("referral"),
            parse_mode="HTML",
        )
        return
    if refs_required <= 0 or reward_days <= 0:
        await message.reply(
            "❌ Values must be positive integers.",
            reply_markup=build_admin_cancel_keyboard("referral"),
            parse_mode="HTML",
        )
        return
    add_referral_tier(session, refs_required=refs_required, reward_days=reward_days)
    await message.reply(
        f"✅ Tier added: <b>{refs_required} refs</b> → <b>{reward_days} days</b> VIP!",
        reply_markup=build_admin_cancel_keyboard("referral"),
        parse_mode="HTML",
    )


@router.callback_query(ReferralNav.filter(F.section == "referrals"))
async def callback_referrals_list(
    query: CallbackQuery, callback_data: ReferralNav, session: Session
) -> None:
    """Paginated list of referral records (who referred whom)."""
    page = max(1, callback_data.page)
    rows, total = list_referrals_paginated(session, page=page, page_size=_PAGE_SIZE)
    total_pages = max(1, math.ceil(total / _PAGE_SIZE))

    lines = [f"👥 <b>Referrals</b> (Total: <code>{total}</code>)\n"]
    if not rows:
        lines.append("⚠️ No referrals registered yet.")
    for idx, ref in enumerate(rows, start=(page - 1) * _PAGE_SIZE + 1):
        referrer = get_user_by_telegram_id(session, ref.referrer_telegram_id)
        referred = get_user_by_telegram_id(session, ref.referred_telegram_id)
        referrer_str = (
            f"@{html.escape(referrer.username)}"
            if referrer and referrer.username
            else f"<code>{ref.referrer_telegram_id}</code>"
        )
        referred_str = (
            f"@{html.escape(referred.username)}"
            if referred and referred.username
            else f"<code>{ref.referred_telegram_id}</code>"
        )
        lines.append(
            f"<b>#{idx}</b> {referrer_str} → {referred_str}\n"
            f"  🕒 {ref.created_at.strftime('%Y-%m-%d %H:%M')}"
        )
    if isinstance(query.message, Message):
        with contextlib.suppress(TelegramBadRequest):
            await query.message.edit_text(
                "\n".join(lines),
                reply_markup=build_referral_list_nav_keyboard("referrals", page, total_pages),
                parse_mode="HTML",
            )
    await query.answer()


@router.callback_query(ReferralNav.filter(F.section == "rewards"))
async def callback_rewards_list(
    query: CallbackQuery, callback_data: ReferralNav, session: Session
) -> None:
    """Paginated list of granted rewards (who received what VIP days)."""
    page = max(1, callback_data.page)
    rows, total = list_referral_rewards_paginated(session, page=page, page_size=_PAGE_SIZE)
    total_pages = max(1, math.ceil(total / _PAGE_SIZE))

    lines = [f"🎁 <b>Granted Rewards</b> (Total events: <code>{total}</code>)\n"]
    if not rows:
        lines.append("⚠️ No rewards granted yet.")
    for idx, rew in enumerate(rows, start=(page - 1) * _PAGE_SIZE + 1):
        referrer = get_user_by_telegram_id(session, rew.referrer_telegram_id)
        referrer_str = (
            f"@{html.escape(referrer.username)}"
            if referrer and referrer.username
            else f"<code>{rew.referrer_telegram_id}</code>"
        )
        lines.append(
            f"<b>#{idx}</b> {referrer_str}  🎁 +<b>{rew.days} days</b> VIP\n"
            f"  🕒 {rew.created_at.strftime('%Y-%m-%d %H:%M')}"
        )
    if isinstance(query.message, Message):
        with contextlib.suppress(TelegramBadRequest):
            await query.message.edit_text(
                "\n".join(lines),
                reply_markup=build_referral_list_nav_keyboard("rewards", page, total_pages),
                parse_mode="HTML",
            )
    await query.answer()


@router.callback_query(F.data == "adm_ref_toggle")
async def callback_referral_toggle(query: CallbackQuery, session: Session) -> None:
    """Enable / disable the whole referral system."""
    enabled = is_referral_enabled(session)
    set_referral_enabled(session, not enabled)
    await query.answer(
        f"🔗 Referral system {'ENABLED' if not enabled else 'DISABLED'}.",
        show_alert=True,
    )
    await _render_referral_menu(query, session)
