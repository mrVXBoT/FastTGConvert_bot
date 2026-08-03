"""app/services/feature_gate.py — Service layer checking dynamic feature access levels (FREE vs VIP_ONLY)."""

from __future__ import annotations

import logging

from sqlalchemy.orm import Session

from app.db.repositories import get_feature_gate, get_user_by_telegram_id

LOGGER = logging.getLogger(__name__)


def is_feature_accessible(session: Session, telegram_id: int, feature_key: str) -> tuple[bool, str]:
    """Check if a specific bot feature is enabled and accessible for the given user.

    Returns (is_accessible, reason_message_key).
    """
    fg = get_feature_gate(session, feature_key)
    if not fg:
        return True, "ok"

    if not fg.is_enabled:
        return False, "feature_disabled"

    if fg.access_level == "VIP_ONLY":
        user = get_user_by_telegram_id(session, telegram_id)
        if not user or not user.is_vip:
            return False, "feature_vip_only"

    return True, "ok"
