"""app/admin/handlers/stats.py — 📊 Statistics Dashboard router (Today, Week, Month)."""

from __future__ import annotations

import contextlib
from datetime import datetime, timedelta, timezone

UTC = timezone.utc  # noqa: UP017

from aiogram import F, Router
from aiogram.exceptions import TelegramBadRequest
from aiogram.types import CallbackQuery, Message
from sqlalchemy.orm import Session

from app.admin.callbacks import AdminNav, StatsNav
from app.admin.keyboards import build_stats_keyboard
from app.db.repositories import get_dashboard_statistics

router = Router()


@router.callback_query(AdminNav.filter(F.action == "stats"))
@router.callback_query(StatsNav.filter())
async def callback_statistics(query: CallbackQuery, session: Session, callback_data: StatsNav | AdminNav | None = None) -> None:
    """Render Statistics dashboard filtered by Today, Week, or Month."""
    period = callback_data.period if isinstance(callback_data, StatsNav) else "today"
    now = datetime.now(UTC)

    if period == "week":
        since_time = now - timedelta(days=7)
        title_hdr = "📆 <b>This Week Statistics</b>"
    elif period == "month":
        since_time = now - timedelta(days=30)
        title_hdr = "📅 <b>This Month Statistics</b>"
    else:
        since_time = now.replace(hour=0, minute=0, second=0, microsecond=0)
        title_hdr = "📅 <b>Today Statistics</b>"

    stats = get_dashboard_statistics(session, since_time)

    text = (
        f"{title_hdr}\n\n"
        f"👤 <b>New Users:</b> <code>{stats['new_users']}</code>\n"
        f"🚀 <b>Active Users:</b> <code>{stats['active_users']}</code>\n"
        f"👥 <b>Total Registered Users:</b> <code>{stats['total_users']}</code>\n"
        f"💎 <b>VIP Members:</b> <code>{stats['vip_users']}</code>\n"
        f"💰 <b>VIP Sales:</b> <code>{stats['vip_purchases']}</code>\n\n"
        f"📦 <b>Tasks Executed:</b> <code>{stats['task_starts']}</code>\n"
        f"✅ <b>Tasks Succeeded:</b> <code>{stats['task_successes']}</code>\n"
        f"❌ <b>Tasks Failed:</b> <code>{stats['task_failures']}</code>"
    )

    if isinstance(query.message, Message):
        with contextlib.suppress(TelegramBadRequest):
            await query.message.edit_text(text, reply_markup=build_stats_keyboard(), parse_mode="HTML")
    await query.answer()
