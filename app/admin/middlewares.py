"""app/admin/middlewares.py — RBAC Permission Middleware for Admin Panel endpoints."""

from __future__ import annotations

import logging
from collections.abc import Awaitable, Callable
from typing import Any

from aiogram import BaseMiddleware
from aiogram.types import CallbackQuery, Message, TelegramObject

from app.admin.rbac import check_nav_permission, has_permission
from app.config import Settings
from app.db.repositories import get_admin_role

LOGGER = logging.getLogger(__name__)


class AdminPermissionMiddleware(BaseMiddleware):
    """Verify admin/owner authorization AND enforce section-level RBAC.

    Injects ``admin_role`` into handler data so individual handlers can perform
    fine-grained permission checks via ``app.admin.rbac.has_permission()``.
    """

    async def __call__(
        self,
        handler: Callable[[TelegramObject, dict[str, Any]], Awaitable[Any]],
        event: TelegramObject,
        data: dict[str, Any],
    ) -> Any:
        user_id: int | None = None
        if isinstance(event, (Message, CallbackQuery)) and event.from_user:
            user_id = event.from_user.id

        if not user_id:
            return None

        settings: Settings = data["settings"]
        session_factory = data["session_factory"]
        owner_id = settings.admin_id

        with session_factory() as session:
            role = get_admin_role(session, user_id, owner_id=owner_id)

            if not role:
                if isinstance(event, CallbackQuery):
                    await event.answer("🚫 Access Denied! Admin Privileges Required.", show_alert=True)
                elif isinstance(event, Message):
                    await event.reply("🚫 Access Denied! Admin Privileges Required.")
                return None

            # ─── Section-level RBAC for AdminNav callbacks ─────────────────
            if isinstance(event, CallbackQuery) and event.data:
                # Check AdminNav actions
                if event.data.startswith("adm_nav:"):
                    try:
                        nav_action = event.data.split(":")[1]
                        if not check_nav_permission(role, nav_action):
                            await event.answer(
                                f"🚫 Your role ({role}) does not have access to this section.",
                                show_alert=True,
                            )
                            return None
                    except IndexError:
                        pass

                # Block admin management for non-SUPER_ADMIN
                elif event.data.startswith("adm_mgmt:") and not has_permission(role, "SUPER_ADMIN"):
                    await event.answer(
                        "🚫 Admin Management requires SUPER_ADMIN or OWNER role.",
                        show_alert=True,
                    )
                    return None

                # Block Force Join management for non-SUPER_ADMIN
                elif event.data.startswith("adm_fj:") and not has_permission(role, "SUPER_ADMIN"):
                    await event.answer(
                        "🚫 Force Join Management requires SUPER_ADMIN or OWNER role.",
                        show_alert=True,
                    )
                    return None

            data["admin_role"] = role
            data["session"] = session
            return await handler(event, data)
