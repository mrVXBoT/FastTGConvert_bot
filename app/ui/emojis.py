"""app/ui/emojis.py — Centralized Emoji Registry with fallback unicode & dynamic custom_emoji_id lookup."""

from __future__ import annotations

import os
from typing import TYPE_CHECKING, Any, ClassVar

if TYPE_CHECKING:
    from sqlalchemy.orm import Session

from app.ui.custom_emoji_mapping import CUSTOM_EMOJI_MAP

# Default mapping: Emoji Key -> Fallback Unicode Emoji
EMOJI_DEFAULTS: dict[str, str] = dict(CUSTOM_EMOJI_MAP)


class EmojiRegistry:
    """Registry managing fallback unicode icons and optional Telegram Custom Emoji IDs."""

    _custom_emoji_ids: ClassVar[dict[str, str]] = {}

    @classmethod
    def set_custom_emoji(cls, key: str, custom_emoji_id: str | None) -> None:
        """Configure or clear a custom_emoji_id for a given icon key."""
        if custom_emoji_id and custom_emoji_id.strip():
            cls._custom_emoji_ids[key.upper()] = custom_emoji_id.strip()
        else:
            cls._custom_emoji_ids.pop(key.upper(), None)

    @classmethod
    def get_fallback_unicode(cls, key: str) -> str:
        """Get the required fallback unicode emoji for a key."""
        return EMOJI_DEFAULTS.get(key.upper(), "✨")

    @classmethod
    def get_custom_emoji_id(cls, key: str) -> str | None:
        """Get the optional Telegram custom_emoji_id for a key, or None if unavailable."""
        return cls._custom_emoji_ids.get(key.upper())

    @classmethod
    def resolve_icon(cls, key: str) -> tuple[str, str | None]:
        """Return (unicode_fallback, optional_custom_emoji_id)."""
        k = key.upper()
        return cls.get_fallback_unicode(k), cls.get_custom_emoji_id(k)

    @classmethod
    def format_text_emoji(cls, key: str) -> str:
        """Format an emoji for Telegram HTML message text.
        Uses <tg-emoji emoji-id="...">fallback</tg-emoji> if custom_emoji_id is configured,
        otherwise returns fallback unicode emoji.
        """
        unicode_fallback, custom_id = cls.resolve_icon(key)
        if custom_id:
            return f'<tg-emoji emoji-id="{custom_id}">{unicode_fallback}</tg-emoji>'
        return unicode_fallback

    @classmethod
    def enrich_text(cls, text: str) -> str:
        """Replace standard unicode emojis in HTML message text with <tg-emoji> custom tags if custom_emoji_id is configured."""
        if not text or not isinstance(text, str):
            return text
        result = text
        unicode_to_key: dict[str, str] = {
            "💎": "VIP",
            "👮": "ADMIN",
            "👑": "ADMIN",
            "👥": "USERS",
            "👤": "USERS",
            "📊": "STATS",
            "📅": "STATS",
            "📆": "STATS",
            "⚡": "STATS",
            "⚙️": "SETTINGS",
            "📢": "BROADCAST",
            "💳": "PAYMENT",
            "💰": "PAYMENT",
            "🎧": "SUPPORT",
            "📌": "FORCE_JOIN",
            "✅": "SUCCESS",
            "🔴": "DANGER",
            "🔍": "SEARCH",
            "🔐": "SECURITY",
            "🔒": "SECURITY",
            "🔑": "SECURITY",
            "❌": "CANCEL",
            "🔄": "CONVERT",
            "✂️": "SPLIT",
            "🔀": "MERGE",
            "🛡️": "SPAM",
            "📨": "OTP",
            "📋": "CONTACTS",
            "📝": "EXPORT",
            "📄": "EXPORT",
            "📦": "SPLIT",
            "🔓": "UNLOCK",
            "♻️": "RESET",
            "🗑️": "DELETE",
        }
        for u_char, key in unicode_to_key.items():
            if u_char in result and f'>{u_char}</tg-emoji>' not in result:
                custom_id = cls.get_custom_emoji_id(key)
                if custom_id:
                    tag = f'<tg-emoji emoji-id="{custom_id}">{u_char}</tg-emoji>'
                    result = result.replace(u_char, tag)
        return result

    @classmethod
    def load_from_env(cls) -> None:
        """Load configured custom_emoji_ids from environment variables (keys matching CUSTOM_EMOJI_<KEY>)."""
        for env_key, val in os.environ.items():
            if env_key.startswith("CUSTOM_EMOJI_") and val and val.strip():
                emoji_key = env_key.removeprefix("CUSTOM_EMOJI_").upper()
                cls.set_custom_emoji(emoji_key, val.strip())

    @classmethod
    def load_from_settings(cls, settings: Any) -> None:
        """Load configured custom_emoji_ids from pydantic Settings object."""
        # First load environment variables
        cls.load_from_env()

        if settings is not None:
            for attr in dir(settings):
                if attr.startswith("custom_emoji_"):
                    val = getattr(settings, attr, "")
                    if val and isinstance(val, str) and val.strip():
                        emoji_key = attr.removeprefix("custom_emoji_").upper()
                        cls.set_custom_emoji(emoji_key, val.strip())

    @classmethod
    def load_from_db(cls, session: Session) -> None:
        """Load custom_emoji_ids from system_settings DB table (key format 'emoji:<KEY>'). Priority 1 (overrides env)."""
        from app.db.models import SystemSetting

        settings = session.query(SystemSetting).filter(SystemSetting.key.like("emoji:%")).all()
        for s in settings:
            emoji_key = s.key.split(":", 1)[1].upper()
            if s.value and s.value.strip():
                cls.set_custom_emoji(emoji_key, s.value.strip())

    @classmethod
    def clear(cls) -> None:
        """Clear all registered custom emoji IDs."""
        cls._custom_emoji_ids.clear()

    @classmethod
    def reset(cls) -> None:
        """Reset registry by clearing registered custom emoji IDs."""
        cls.clear()
