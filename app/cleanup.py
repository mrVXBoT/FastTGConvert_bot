import asyncio
import logging
from datetime import UTC, datetime
from pathlib import Path

from sqlalchemy import select
from sqlalchemy.orm import Session, sessionmaker

from app.db.models import FileRecord, User, UserVIPSubscription

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


async def cleanup_loop(
    session_factory: sessionmaker[Session], interval_seconds: int = 300
) -> None:
    while True:
        try:
            await cleanup_expired_files(session_factory)
            await cleanup_expired_vip_subscriptions(session_factory)
        except Exception as exc:  # noqa: BLE001
            LOGGER.error("Cleanup loop error: %s", exc)
        await asyncio.sleep(interval_seconds)
