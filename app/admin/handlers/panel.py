"""app/admin/handlers/panel.py — Main Admin Panel command (/admin) & home router with i18n support."""

from __future__ import annotations

import contextlib
import html

from aiogram import F, Router
from aiogram.exceptions import TelegramBadRequest
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery, Message
from sqlalchemy.orm import Session

from app.admin.callbacks import AdminNav
from app.admin.keyboards import build_admin_main_menu_keyboard
from app.db.repositories import get_user_language
from app.locales import get_admin_locale

router = Router()


@router.message(Command("admin"))
async def command_admin(message: Message, state: FSMContext, session: Session, admin_role: str) -> None:
    """Handle /admin command to open main Admin Panel menu."""
    await state.clear()
    lang = get_user_language(session, message.from_user.id) if message.from_user else "en"
    loc = get_admin_locale(lang)
    text = (
        f"{loc['title']}\n\n"
        f"Role Level: <code>{html.escape(admin_role)}</code>\n\n"
        f"Select a management module below:"
    )
    await message.answer(text, reply_markup=build_admin_main_menu_keyboard(lang=lang, admin_role=admin_role), parse_mode="HTML")


@router.callback_query(AdminNav.filter(F.action == "home"))
async def callback_admin_home(query: CallbackQuery, state: FSMContext, session: Session, admin_role: str) -> None:
    """Return to main Admin Panel home screen."""
    await state.clear()
    lang = get_user_language(session, query.from_user.id)
    loc = get_admin_locale(lang)
    text = (
        f"{loc['title']}\n\n"
        f"Role Level: <code>{html.escape(admin_role)}</code>\n\n"
        f"Select a management module below:"
    )
    if isinstance(query.message, Message):
        with contextlib.suppress(TelegramBadRequest):
            await query.message.edit_text(text, reply_markup=build_admin_main_menu_keyboard(lang=lang, admin_role=admin_role), parse_mode="HTML")
    await query.answer()


@router.callback_query(AdminNav.filter(F.action == "close"))
async def callback_admin_close(query: CallbackQuery, state: FSMContext) -> None:
    """Close Admin Panel message."""
    await state.clear()
    if isinstance(query.message, Message):
        with contextlib.suppress(TelegramBadRequest):
            await query.message.delete()
    await query.answer("Admin Panel Closed.")
