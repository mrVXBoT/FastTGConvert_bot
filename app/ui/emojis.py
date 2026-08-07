"""app/ui/emojis.py — Centralized Emoji Registry with fallback unicode & dynamic custom_emoji_id lookup."""

from __future__ import annotations

import os
import re
from typing import TYPE_CHECKING, Any, ClassVar

if TYPE_CHECKING:
    from sqlalchemy.orm import Session

from app.ui.custom_emoji_mapping import CUSTOM_EMOJI_MAP
from app.ui.flag_pack import FLAG_EMOJI_PACK

# Default mapping: Emoji Key -> Fallback Unicode Emoji
EMOJI_DEFAULTS: dict[str, str] = dict(CUSTOM_EMOJI_MAP)


class EmojiRegistry:
    """Registry managing fallback unicode icons and optional Telegram Custom Emoji IDs."""

    _custom_emoji_ids: ClassVar[dict[str, str]] = {"VIP": "5413351005779672594"}
    _flag_ids: ClassVar[dict[str, str]] = {}

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
    def divider_line(cls, repeats: int = 2) -> str:
        """
        Decorative header divider ("topic\n┈┈┈\nbody" pattern).

        Renders the configured ``DIVIDER`` custom emoji strip (comma-separated
        IDs) side by side, repeated to span the message width.  Falls back to
        a plain sparkle line when no custom emojis are configured.
        """
        custom = cls.get_custom_emoji_id("DIVIDER")
        ids = [e.strip() for e in custom.split(",") if e.strip()] if custom else []
        if ids:
            strip = "".join(
                f'<tg-emoji emoji-id="{eid}">✨</tg-emoji>' for eid in ids
            )
            return strip * repeats
        return "✨" * 12

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
    def _replace_emoji(cls, text: str, u_char: str, custom_id: str) -> str:
        """Replace a unicode emoji with its premium tag, never matching a longer
        (e.g. VS16-suffixed) emoji that starts with the same code points."""
        tag = f'<tg-emoji emoji-id="{custom_id}">{u_char}</tg-emoji>'
        if u_char.endswith("\ufe0f"):
            return text.replace(u_char, tag)
        return re.sub(
            re.escape(u_char) + r"(?!\ufe0f)", lambda _m: tag, text
        )

    @classmethod
    def enrich_text(cls, text: str) -> str:
        """Replace standard unicode emojis in HTML message text with <tg-emoji> custom tags if custom_emoji_id is configured."""
        if not text or not isinstance(text, str):
            return text
        result = text
        for u_char, key in sorted(
            cls.EMOJI_UNICODE_KEYS.items(),
            key=lambda item: len(item[0]),
            reverse=True,
        ):
            if u_char in result and f'>{u_char}</tg-emoji>' not in result:
                custom_id = cls.get_custom_emoji_id(key)
                if custom_id:
                    result = cls._replace_emoji(result, u_char, custom_id)
        return result

    # Standard unicode -> semantic key map for message-text enrichment
    EMOJI_UNICODE_KEYS: ClassVar[dict[str, str]] = {
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
        "⏳": "LOADING",
        "🟢": "ACTIVE",
        "🟡": "FROZEN",
        "🚫": "BANNED",
        "❓": "INCONCLUSIVE",
        "📱": "PHONE",
        "🔖": "USERNAME",
        "🧩": "OTP_CODE",
        "📁": "SESSION",
        "⬇️": "OTP",
        "🔨": "CONTACT_CHECKED",
        "⚠️": "INVALID",
        "📩": "MESSAGE",
        "➕": "ADD",
        "✏️": "EDIT",
        "⏭": "SKIP",
        "⏭️": "SKIP",
        "⚪": "INCONCLUSIVE",
        "🆔": "SESSION",
        "🌐": "LANGUAGE",
        "🏷️": "USERNAME",
        "💵": "PAYMENT",
        "🕒": "STATS",
        "🗓️": "STATS",
        "🚀": "BROADCAST",
        "🔱": "ADMIN",
        "🔗": "LINK",
        "🚪": "EXIT",
        "📂": "FOLDER",
        "🧹": "CLEAN",
        "🤖": "BOT",
        "☑️": "CHECKBOX",
        "✖️": "CLEAR",
        "▫️": "UNCHECK",
        "◻️": "UNCHECK",
        "📇": "CARD",
        "ℹ️": "INFO",
        "🎭": "PROFILE",
        "🖼️": "PHOTO",
        "🖼": "PHOTO",
        "➡️": "NEXT",
        "⭐": "STAR",
        "⏮": "FIRST",
        "◀": "PREV",
        "◀️": "PREV",
        "▶": "NEXT_PAGE",
        "▶️": "NEXT_PAGE",
        "⏱": "TIMER",
        "⚖️": "BALANCED",
        "⏸": "PAUSE",
        "⛔": "STOP",
        "☠️": "KILL",
        # Privacy settings + misc icons that should resolve to env premium IDs
        "👁️": "VIEW",
        "👁": "VIEW",
        "📞": "CALLS",
        "💬": "MESSAGE",
        "🎙️": "VOICE",
        "🎙": "VOICE",
        "🌍": "WORLD",
        "⬅️": "BACK",
        "⌛": "LOADING",
        "😕": "INCONCLUSIVE",
        # Referral system premium icons (resolved via GIFT / TROPHY / MEDAL custom emoji IDs)
        "🎁": "GIFT",
        "🏆": "TROPHY",
        "🥇": "MEDAL",
    }

    # Conversion report metrics: (unicode in locale summary, semantic key)
    REPORT_EMOJI_KEYS: ClassVar[tuple[tuple[str, str], ...]] = (
        ("📦", "TOTAL"),
        ("✅", "CONVERTED"),
        ("⚠️", "INVALID"),
        ("❌", "FAILED"),
    )

    # Additional tool-flow emojis upgraded to premium alongside report metrics
    EXTRA_ENRICH_KEYS: ClassVar[tuple[tuple[str, str], ...]] = (
        ("✂️", "SPLIT"),
        ("🗺️", "SPLIT_COUNTRY"),
        ("🔢", "SPLIT_QUANTITY"),
        ("🔀", "MERGE"),
        ("⏳", "LOADING"),
    )

    @classmethod
    def enrich_report(cls, text: str) -> str:
        """Upgrade conversion-report metric emojis to premium <tg-emoji> tags when custom IDs are configured."""
        if not text or not isinstance(text, str):
            return text
        for u_char, key in cls.REPORT_EMOJI_KEYS:
            custom_id = cls.get_custom_emoji_id(key)
            if custom_id and u_char in text:
                tag = f'<tg-emoji emoji-id="{custom_id}">{u_char}</tg-emoji>'
                text = text.replace(u_char, tag)
        return text

    @classmethod
    def enrich(cls, text: str) -> str:
        """Upgrade report metrics, tool-flow emojis and standard icons to premium <tg-emoji> tags."""
        if not text or not isinstance(text, str):
            return text
        priority = {
            key: index
            for index, (_u, key) in enumerate(
                (*cls.REPORT_EMOJI_KEYS, *cls.EXTRA_ENRICH_KEYS)
            )
        }
        pairs: list[tuple[str, str]] = list(cls.REPORT_EMOJI_KEYS)
        pairs.extend(cls.EXTRA_ENRICH_KEYS)
        for u_char, key in cls.EMOJI_UNICODE_KEYS.items():
            if u_char not in priority and (u_char, key) not in pairs:
                pairs.append((u_char, key))
        for u_char, key in sorted(pairs, key=lambda pair: len(pair[0]), reverse=True):
            if u_char in text and f'>{u_char}</tg-emoji>' not in text:
                custom_id = cls.get_custom_emoji_id(key)
                if custom_id:
                    text = cls._replace_emoji(text, u_char, custom_id)
        return text

    @classmethod
    def load_flag_pack(cls, enabled: bool = True) -> None:
        """Register premium country-flag IDs from the flag pack."""
        if enabled:
            cls._flag_ids = dict(FLAG_EMOJI_PACK)
        else:
            cls._flag_ids.clear()

    @classmethod
    def get_flag_custom_id(cls, flag: str) -> str | None:
        """Get the premium custom emoji id for a unicode flag emoji, or None."""
        return cls._flag_ids.get(flag)

    @classmethod
    def enrich_flags(cls, text: str) -> str:
        """Upgrade unicode country flags in HTML text to premium <tg-emoji> tags.
        Idempotent: already-tagged flags are left untouched."""
        if not text or not isinstance(text, str) or not cls._flag_ids:
            return text
        for flag, custom_id in cls._flag_ids.items():
            if flag in text and f">{flag}</tg-emoji>" not in text:
                tag = f'<tg-emoji emoji-id="{custom_id}">{flag}</tg-emoji>'
                text = text.replace(flag, tag)
        return text

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
        cls.load_flag_pack()

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
        cls._flag_ids.clear()

    @classmethod
    def reset(cls) -> None:
        """Reset registry by clearing registered custom emoji IDs."""
        cls.clear()
