"""app/ui — Centralized UI Design System package for FastTGConvert."""

from app.ui.custom_emoji_mapping import CUSTOM_EMOJI_MAP
from app.ui.custom_emojis import DEFAULT_CUSTOM_EMOJIS
from app.ui.custom_emojis import DEFAULT_CUSTOM_EMOJIS as CUSTOM_EMOJIS
from app.ui.emojis import EmojiRegistry
from app.ui.entities import create_custom_emoji_entity, format_text_with_custom_emojis
from app.ui.factory import Button, create_admin_button, create_user_button
from app.ui.styles import ButtonStyle
from app.ui.theme import (
    BACK_COLOR,
    DANGER_COLOR,
    DELETE_COLOR,
    PRIMARY_COLOR,
    SUCCESS_COLOR,
    VIP_COLOR,
    Theme,
)

__all__ = [
    "BACK_COLOR",
    "CUSTOM_EMOJIS",
    "CUSTOM_EMOJI_MAP",
    "DANGER_COLOR",
    "DEFAULT_CUSTOM_EMOJIS",
    "DELETE_COLOR",
    "PRIMARY_COLOR",
    "SUCCESS_COLOR",
    "VIP_COLOR",
    "Button",
    "ButtonStyle",
    "EmojiRegistry",
    "Theme",
    "create_admin_button",
    "create_custom_emoji_entity",
    "create_user_button",
    "format_text_with_custom_emojis",
]
