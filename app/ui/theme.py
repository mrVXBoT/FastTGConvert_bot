"""app/ui/theme.py — Centralized UI Theme & Style Configuration for FastTGConvert."""

from __future__ import annotations

from app.ui.styles import ButtonStyle


class Theme:
    """SaaS Premium Theme mapping semantic button actions to Telegram button styles and emoji keys."""

    # Button Style Mappings
    VIP_STYLE: ButtonStyle = ButtonStyle.SUCCESS
    DANGER_STYLE: ButtonStyle = ButtonStyle.DANGER
    NAV_STYLE: ButtonStyle = ButtonStyle.PRIMARY
    ACTION_SUCCESS_STYLE: ButtonStyle = ButtonStyle.SUCCESS
    ACTION_PRIMARY_STYLE: ButtonStyle = ButtonStyle.PRIMARY

    # Semantic Emoji Key Mappings
    EMOJI_VIP: str = "VIP"
    EMOJI_DANGER: str = "BAN"
    EMOJI_DELETE: str = "DELETE"
    EMOJI_SETTINGS: str = "SETTINGS"
    EMOJI_STATS: str = "STATS"
    EMOJI_PAYMENT: str = "PAYMENT"
    EMOJI_BACK: str = "BACK"
    EMOJI_CANCEL: str = "CANCEL"
    EMOJI_SUCCESS: str = "SUCCESS"
    EMOJI_BROADCAST: str = "BROADCAST"
    EMOJI_SUPPORT: str = "SUPPORT"
    EMOJI_FORCE_JOIN: str = "FORCE_JOIN"
    EMOJI_ADMIN: str = "ADMIN"
    EMOJI_USERS: str = "USERS"


# Semantic Style Constant Aliases
VIP_COLOR = Theme.VIP_STYLE
DELETE_COLOR = Theme.DANGER_STYLE
DANGER_COLOR = Theme.DANGER_STYLE
BACK_COLOR = Theme.NAV_STYLE
PRIMARY_COLOR = Theme.NAV_STYLE
SUCCESS_COLOR = Theme.ACTION_SUCCESS_STYLE
