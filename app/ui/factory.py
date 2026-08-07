"""app/ui/factory.py — Centralized Button Factory for building styled, icon-enabled InlineKeyboardButtons."""

from __future__ import annotations

from typing import TYPE_CHECKING

from aiogram.types import InlineKeyboardButton

from app.ui.emojis import EmojiRegistry
from app.ui.styles import ButtonStyle

if TYPE_CHECKING:
    from collections.abc import Mapping


class Button:
    """Central Button Factory for creating Telegram InlineKeyboardButtons."""

    @staticmethod
    def create(
        text: str,
        callback_data: str | None = None,
        *,
        style: ButtonStyle | str | None = None,
        emoji_key: str | None = None,
        include_emoji: bool = True,
        custom_emoji_id: str | None = None,
        url: str | None = None,
    ) -> InlineKeyboardButton:
        """Create a styled InlineKeyboardButton.

        Rules:
        1. If custom_emoji_id exists (via parameter or EmojiRegistry):
           - DO NOT prepend unicode emoji.
           - Button text contains only the clean label.
           - Uses icon_custom_emoji_id only.
        2. If custom_emoji_id does not exist:
           - Prepend unicode fallback emoji if requested.
        """
        btn_text = text
        icon_custom_id = custom_emoji_id

        if emoji_key:
            unicode_icon, registered_custom_id = EmojiRegistry.resolve_icon(emoji_key)
            if not icon_custom_id:
                icon_custom_id = registered_custom_id

            # Only prepend unicode fallback emoji if custom_emoji_id is NOT available
            if (
                not icon_custom_id
                and include_emoji
                and not any(char in btn_text[:3] for char in (unicode_icon, "💎", "🚫", "🗑️", "✅", "⚠️", "⚙️", "⬅️", "📊"))
            ):
                btn_text = f"{unicode_icon} {btn_text}"

        style_val = style.value if isinstance(style, ButtonStyle) else style

        kwargs: dict[str, str | None] = {
            "text": btn_text,
        }
        if url:
            kwargs["url"] = url
        elif callback_data:
            kwargs["callback_data"] = callback_data

        if style_val:
            kwargs["style"] = style_val
        if icon_custom_id:
            kwargs["icon_custom_emoji_id"] = icon_custom_id

        return InlineKeyboardButton(**kwargs)  # type: ignore[arg-type]

    @classmethod
    def create_localized(
        cls,
        loc_dict: Mapping[str, str],
        loc_key: str,
        callback_data: str,
        *,
        style: ButtonStyle | str | None = None,
        emoji_key: str | None = None,
        fallback_text: str = "",
    ) -> InlineKeyboardButton:
        """Create button by looking up loc_key in locale dictionary."""
        text = loc_dict.get(loc_key, fallback_text or loc_key)
        return cls.create(
            text=text,
            callback_data=callback_data,
            style=style,
            emoji_key=emoji_key,
        )


create_admin_button = Button.create
create_user_button = Button.create
