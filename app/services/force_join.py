"""app/services/force_join.py — Unified force-join channel resolution (DB channels + env channels)."""

from __future__ import annotations

from sqlalchemy.orm import Session

from app.config import Settings
from app.db.repositories import list_force_join_channels


def get_active_force_join_channels(session: Session, settings: Settings) -> list[str]:
    """Merge active DB channels with env-configured channels.

    Returns a de-duplicated, ordered list of channel identifiers
    (e.g. ``@username`` or ``-100123456789``). DB channels come first, and
    channels already present in the DB (even if inactive) are never
    re-introduced from the env list — the DB state wins.
    """
    db_channels = list_force_join_channels(session, active_only=False)
    db_ids = {ch.channel_id for ch in db_channels if ch.channel_id}
    channels = [
        ch.channel_id
        for ch in db_channels
        if ch.is_active and ch.channel_id
    ]
    for channel in settings.required_channel_list:
        if channel and channel not in db_ids and channel not in channels:
            channels.append(channel)
    return channels


def get_force_join_invite_links(session: Session) -> dict[str, str]:
    """Map active DB channel ids to their stored invite links (if any)."""
    return {
        ch.channel_id: ch.invite_link
        for ch in list_force_join_channels(session, active_only=True)
        if ch.channel_id and ch.invite_link
    }
