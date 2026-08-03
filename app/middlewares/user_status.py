"""app/middlewares/user_status.py — Middleware for blocking BANNED users across all user routers."""

from __future__ import annotations

import logging
from collections.abc import Awaitable, Callable
from typing import Any

from aiogram import BaseMiddleware
from aiogram.types import CallbackQuery, Message, TelegramObject

from app.config import Settings
from app.db.repositories import get_admin_role, get_user_by_telegram_id

LOGGER = logging.getLogger(__name__)


class UserStatusMiddleware(BaseMiddleware):
    """Middleware to enforce User Status (BANNED users are blocked from executing any user handlers)."""

    async def __call__(
        self,
        handler: Callable[[TelegramObject, dict[str, Any]], Awaitable[Any]],
        event: TelegramObject,
        data: dict[str, Any],
    ) -> Any:
        from_user = getattr(event, "from_user", None)
        if not from_user:
            return await handler(event, data)

        user_id = from_user.id
        settings: Settings | None = data.get("settings")
        session_factory = data.get("session_factory")

        if not session_factory:
            return await handler(event, data)

        owner_id = settings.admin_id if settings else None

        with session_factory() as session:
            # 1. Admin / Owner Bypass Check (Admins/Owners can access even if status changed)
            role = get_admin_role(session, user_id, owner_id=owner_id)
            if role in ("OWNER", "ADMIN"):
                return await handler(event, data)

            # 2. Regular User Ban Check
            user = get_user_by_telegram_id(session, user_id)
            if user and user.status == "banned":
                LOGGER.warning("Blocked BANNED user %d from executing handler", user_id)
                if isinstance(event, CallbackQuery):
                    await event.answer("⛔ Your account has been suspended by an administrator.", show_alert=True)
                elif isinstance(event, Message):
                    await event.answer(
                        "⛔ <b>Account Suspended</b>\n\nYour account has been suspended by an administrator. Please contact support if you believe this is an error.",
                        parse_mode="HTML",
                    )
                return None

            return await handler(event, data)
