"""app/admin/handlers/language.py — 🌐 Multi-Language Admin Panel interface router."""

from __future__ import annotations

import contextlib
import html

from aiogram import F, Router
from aiogram.exceptions import TelegramBadRequest
from aiogram.types import CallbackQuery, Message
from sqlalchemy.orm import Session

from app.admin.callbacks import AdminLangAction, AdminNav
from app.admin.keyboards import (
    build_admin_language_keyboard,
    build_admin_main_menu_keyboard,
)
from app.db.repositories import get_user_language, set_user_language
from app.locales import get_admin_locale

router = Router()


@router.callback_query(AdminNav.filter(F.action == "language"))
async def callback_admin_language_menu(query: CallbackQuery, session: Session) -> None:
    """Render Admin Language Selector menu."""
    lang = get_user_language(session, query.from_user.id) if query.from_user else "en"
    text = (
        "🌐 <b>Admin Panel Language Switcher</b>\n\n"
        "Select your preferred interface language for Admin Panel:"
    )
    if isinstance(query.message, Message):
        with contextlib.suppress(TelegramBadRequest):
            await query.message.edit_text(
                text,
                reply_markup=build_admin_language_keyboard(current_lang=lang),
                parse_mode="HTML",
            )
    await query.answer()


@router.callback_query(AdminLangAction.filter())
async def callback_admin_set_language(
    query: CallbackQuery, callback_data: AdminLangAction, session: Session, admin_role: str
) -> None:
    """Set language for admin and return directly to Admin Panel home screen."""
    new_lang = callback_data.lang
    if query.from_user:
        set_user_language(session, query.from_user.id, query.from_user.username, new_lang)

    loc = get_admin_locale(new_lang)
    text = (
        f"{loc['title']}\n\n"
        f"Role Level: <code>{html.escape(admin_role)}</code>\n\n"
        f"Select a management module below:"
    )
    await query.answer(f"Language updated to {new_lang.upper()}")
    if isinstance(query.message, Message):
        with contextlib.suppress(TelegramBadRequest):
            await query.message.edit_text(
                text,
                reply_markup=build_admin_main_menu_keyboard(lang=new_lang, admin_role=admin_role),
                parse_mode="HTML",
            )
