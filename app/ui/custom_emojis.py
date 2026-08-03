"""app/ui/custom_emojis.py — Default Telegram Premium Custom Emoji Registry."""

from __future__ import annotations

# Dynamic custom emoji ID registry map (empty by default; loaded at runtime from DB & env).
DEFAULT_CUSTOM_EMOJIS: dict[str, str] = {}
