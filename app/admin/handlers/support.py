"""app/admin/handlers/support.py — 🎧 Support Settings router connected to system_settings DB table."""

from __future__ import annotations

import contextlib
import html

from aiogram import F, Router
from aiogram.exceptions import TelegramBadRequest
from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery, Message
from sqlalchemy.orm import Session

from app.admin.callbacks import AdminNav
from app.admin.keyboards import (
    build_admin_cancel_keyboard,
    build_admin_main_menu_keyboard,
)
from app.admin.states import SetSupportState
from app.db.repositories import get_support_contact, set_support_contact

router = Router()


@router.callback_query(AdminNav.filter(F.action == "support"))
async def callback_support_settings(query: CallbackQuery, state: FSMContext, session: Session) -> None:
    """Render Support settings with Cancel button."""
    await state.set_state(SetSupportState.waiting_for_support_id)
    current_support = get_support_contact(session)
    text = (
        f"🎧 <b>Support Contact Settings</b>\n\n"
        f"Current Support Contact: <code>{html.escape(current_support or 'N/A')}</code>\n\n"
        f"To change support contact, please send new username (e.g., <code>@admin_support</code>):"
    )
    if isinstance(query.message, Message):
        with contextlib.suppress(TelegramBadRequest):
            await query.message.edit_text(
                text,
                reply_markup=build_admin_cancel_keyboard("home"),
                parse_mode="HTML",
            )
    await query.answer()


@router.message(SetSupportState.waiting_for_support_id)
async def process_support_input(message: Message, state: FSMContext, session: Session, admin_role: str) -> None:
    """Update support username dynamically in database."""
    await state.clear()
    new_supp = (message.text or "").strip()
    if not new_supp.startswith("@"):
        new_supp = f"@{new_supp}"
    set_support_contact(session, new_supp)
    await message.reply(
        f"✅ Support username updated to <code>{html.escape(new_supp)}</code> in database!",
        reply_markup=build_admin_main_menu_keyboard(admin_role=admin_role),
        parse_mode="HTML",
    )
