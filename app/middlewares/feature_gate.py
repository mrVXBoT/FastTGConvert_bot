"""app/middlewares/feature_gate.py — Middleware enforcing dynamic Feature Gate access controls (FREE vs VIP_ONLY)."""

from __future__ import annotations

import logging
from collections.abc import Awaitable, Callable
from typing import Any

from aiogram import BaseMiddleware
from aiogram.types import CallbackQuery, TelegramObject

from app.config import Settings
from app.db.repositories import (
    get_admin_role,
    get_user_language,
    list_vip_plans,
)
from app.keyboards import user_vip_plans_menu
from app.locales import FEATURE_DISABLED_MESSAGES, VIP_RESTRICTED_MESSAGES
from app.services.feature_gate import is_feature_accessible

LOGGER = logging.getLogger(__name__)

QUICK_ACTION_MAP: dict[str, str] = {
    "file_split": "split",
    "file_merge": "file_merge",
}


class FeatureGateMiddleware(BaseMiddleware):
    """Middleware enforcing feature accessibility based on FeatureGate access level and VIP status."""

    async def __call__(
        self,
        handler: Callable[[TelegramObject, dict[str, Any]], Awaitable[Any]],
        event: TelegramObject,
        data: dict[str, Any],
    ) -> Any:
        session_factory = data.get("session_factory")
        if not session_factory:
            return await handler(event, data)

        from_user = getattr(event, "from_user", None)
        if not from_user:
            return await handler(event, data)

        user_id = from_user.id
        settings: Settings | None = data.get("settings")
        owner_id = settings.admin_id if settings else None

        feature_key: str | None = None

        if isinstance(event, CallbackQuery) and event.data:
            cb_data = event.data
            if cb_data.startswith("tool:"):
                feature_key = cb_data.split("tool:", 1)[1]
            elif cb_data.startswith("quick:"):
                action = cb_data.split("quick:", 1)[1]
                feature_key = QUICK_ACTION_MAP.get(action, action)
            elif cb_data == "menu:account_age":
                feature_key = "account_age"

        if feature_key:
            with session_factory() as session:
                # 1. Admin / Owner bypass check
                role = get_admin_role(session, user_id, owner_id=owner_id)
                if role in ("OWNER", "SUPER_ADMIN", "ADMIN"):
                    return await handler(event, data)

                # 2. Feature accessibility check
                accessible, reason = is_feature_accessible(session, user_id, feature_key)
                if not accessible:
                    LOGGER.warning("Blocked user %d from feature '%s' (reason: %s)", user_id, feature_key, reason)
                    lang = get_user_language(session, user_id) or "en"

                    if isinstance(event, CallbackQuery):
                        await event.answer()
                        if reason == "feature_vip_only":
                            plans = list_vip_plans(session, active_only=True)
                            prompt_text = VIP_RESTRICTED_MESSAGES.get(lang, VIP_RESTRICTED_MESSAGES["en"])
                            kb = user_vip_plans_menu(plans, language=lang)
                            if event.message and hasattr(event.message, "edit_text"):
                                await event.message.edit_text(prompt_text, reply_markup=kb, parse_mode="HTML")
                            elif event.bot:
                                await event.bot.send_message(chat_id=user_id, text=prompt_text, reply_markup=kb, parse_mode="HTML")
                        elif reason == "feature_disabled":
                            disabled_text = FEATURE_DISABLED_MESSAGES.get(lang, FEATURE_DISABLED_MESSAGES["en"])
                            if event.message and hasattr(event.message, "edit_text"):
                                await event.message.edit_text(disabled_text, parse_mode="HTML")
                            elif event.bot:
                                await event.bot.send_message(chat_id=user_id, text=disabled_text, parse_mode="HTML")
                    return None

        return await handler(event, data)
