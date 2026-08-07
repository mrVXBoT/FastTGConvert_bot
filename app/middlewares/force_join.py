"""app/middlewares/force_join.py — Enforce force-join channels (DB + env) on all user events."""

from __future__ import annotations

import logging
from collections.abc import Awaitable, Callable
from contextlib import suppress
from typing import Any

from aiogram import BaseMiddleware
from aiogram.types import CallbackQuery, Message, TelegramObject

from app.config import Settings
from app.db.repositories import get_admin_role, get_user_language
from app.keyboards import membership_menu
from app.locales import get_locale
from app.services.force_join import (
    get_active_force_join_channels,
    get_force_join_invite_links,
)
from app.services.membership import missing_memberships

LOGGER = logging.getLogger(__name__)

ADMIN_ROLES = ("OWNER", "SUPER_ADMIN", "ADMIN", "SUPPORT")


class ForceJoinMiddleware(BaseMiddleware):
    """Block user events until the user joins every active force-join channel.

    ``/start``, ``/language``, the membership-check callback and the language
    picker are always allowed through (they either handle the gate themselves
    or are required to complete it).
    """

    async def __call__(
        self,
        handler: Callable[[TelegramObject, dict[str, Any]], Awaitable[Any]],
        event: TelegramObject,
        data: dict[str, Any],
    ) -> Any:
        session_factory = data.get("session_factory")
        bot = data.get("bot")
        settings: Settings | None = data.get("settings")
        if not session_factory or not bot or not settings:
            return await handler(event, data)

        from_user = getattr(event, "from_user", None)
        if not from_user:
            return await handler(event, data)

        user_id = from_user.id

        if isinstance(event, CallbackQuery):
            cb_data = event.data or ""
            if cb_data.startswith(("membership:check:", "language:")):
                return await handler(event, data)
        elif isinstance(event, Message):
            text = (event.text or "").strip().lower()
            if text.startswith(("/start", "/language")):
                return await handler(event, data)

        with session_factory() as session:
            role = get_admin_role(session, user_id, owner_id=settings.admin_id)
            if role in ADMIN_ROLES:
                return await handler(event, data)

            channels = get_active_force_join_channels(session, settings)
            if not channels:
                return await handler(event, data)

        missing = await missing_memberships(bot, user_id, tuple(channels))
        if not missing:
            return await handler(event, data)

        with session_factory() as session:
            language = get_user_language(session, user_id) or "en"
            invite_links = get_force_join_invite_links(session)
        locale = get_locale(language)
        channel_names = "\n".join(f"📢 {channel}" for channel in channels)
        text = locale.join_required
        if channel_names:
            text = f"{text}\n\n{channel_names}"
        kb = membership_menu(tuple(channels), language, invite_links)

        if isinstance(event, CallbackQuery):
            await event.answer()
            message = getattr(event, "message", None)
            if message and hasattr(message, "edit_text"):
                with suppress(Exception):
                    await message.edit_text(text, reply_markup=kb)
            elif not message:
                await bot.send_message(
                    chat_id=user_id, text=text, reply_markup=kb
                )
        elif isinstance(event, Message):
            await event.answer(text, reply_markup=kb)
        return None
