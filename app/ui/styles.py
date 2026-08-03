"""app/ui/styles.py — Button style definitions for Telegram Inline Keyboard buttons."""

from enum import Enum


class ButtonStyle(str, Enum):
    """Centralized Button Styles compatible with Telegram Bot API 7.0+ / 8.0+ / Aiogram 3.30+."""

    PRIMARY = "primary"
    SUCCESS = "success"
    DANGER = "danger"
