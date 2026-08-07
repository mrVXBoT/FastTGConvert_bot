import asyncio
import logging
from contextlib import suppress
from datetime import datetime, timedelta, timezone

UTC = timezone.utc  # noqa: UP017
from pathlib import Path

from sqlalchemy import select
from sqlalchemy.orm import Session, sessionmaker

from app.db.models import FileRecord, User, UserVIPSubscription
from app.db.repositories import expire_auto_payments

LOGGER = logging.getLogger(__name__)


async def cleanup_expired_files(
    session_factory: sessionmaker[Session],
) -> int:
    removed = 0
    with session_factory() as session:
        records = list(
            session.scalars(
                select(FileRecord).where(
                    FileRecord.expires_at <= datetime.now(UTC),
                    FileRecord.storage_path != "",
                )
            )
        )
        for record in records:
            Path(record.storage_path).unlink(missing_ok=True)
            record.storage_path = ""
            removed += 1
        session.commit()
    return removed


async def cleanup_expired_vip_subscriptions(
    session_factory: sessionmaker[Session],
) -> int:
    """Scan and expire outdated VIP subscriptions, syncing user VIP flags."""
    expired_count = 0
    now = datetime.now(UTC)
    with session_factory() as session:
        expired_subs = list(
            session.scalars(
                select(UserVIPSubscription).where(
                    UserVIPSubscription.status == "active",
                    UserVIPSubscription.expires_at <= now,
                )
            )
        )
        for sub in expired_subs:
            sub.status = "expired"
            user = session.scalar(select(User).where(User.id == sub.user_id))
            if user:
                has_other_active = session.scalar(
                    select(UserVIPSubscription).where(
                        UserVIPSubscription.user_id == user.id,
                        UserVIPSubscription.status == "active",
                        UserVIPSubscription.id != sub.id,
                    )
                )
                if not has_other_active:
                    user.is_vip = False
            expired_count += 1
        session.commit()
    if expired_count > 0:
        LOGGER.info("Expired %d outdated VIP subscriptions.", expired_count)
    return expired_count


async def cleanup_expired_auto_payments(
    session_factory: sessionmaker[Session],
    grace_seconds: int = 0,
) -> int:
    """Cancel auto payment orders that outlived their validity window (+ grace)."""
    expired_count = 0
    with session_factory() as session:
        expired_count = expire_auto_payments(session, grace_seconds=grace_seconds)
    if expired_count > 0:
        LOGGER.info("Expired %d auto payment orders.", expired_count)
    return expired_count


def cleanup_orphaned_staged_sessions(
    storage_dir: Path, max_age_minutes: int = 360
) -> int:
    """Sweep abandoned session files staged by interactive flows (e.g. OTP).

    ``download_document`` stores each upload in the inbox before the user
    finishes the OTP view/skip/logout loop. Flows that are abandoned (user
    closes the chat, cancels, restarts) leave these live ``.session`` files on
    disk forever, so stale copies are deleted after *max_age_minutes*.
    """
    if not storage_dir.exists():
        return 0
    cutoff = datetime.now(UTC) - timedelta(minutes=max_age_minutes)
    removed = 0
    for candidate in storage_dir.rglob("*.session"):
        if candidate.is_file():
            mtime = datetime.fromtimestamp(candidate.stat().st_mtime, tz=UTC)
            if mtime <= cutoff:
                with suppress(OSError):
                    candidate.unlink(missing_ok=True)
                    removed += 1
    if removed:
        LOGGER.info("Removed %d orphaned staged .session files.", removed)
    return removed


async def cleanup_loop(
    session_factory: sessionmaker[Session],
    interval_seconds: int = 300,
    payment_expiry_grace_seconds: int = 0,
    storage_dir: Path | None = None,
    staged_session_max_age_minutes: int = 360,
) -> None:
    while True:
        try:
            await cleanup_expired_files(session_factory)
            await cleanup_expired_vip_subscriptions(session_factory)
            await cleanup_expired_auto_payments(
                session_factory, grace_seconds=payment_expiry_grace_seconds
            )
            if storage_dir is not None:
                await asyncio.to_thread(
                    cleanup_orphaned_staged_sessions,
                    storage_dir,
                    staged_session_max_age_minutes,
                )
        except Exception as exc:  # noqa: BLE001
            LOGGER.error("Cleanup loop error: %s", exc)
        await asyncio.sleep(interval_seconds)
