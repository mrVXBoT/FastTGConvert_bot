import asyncio
from datetime import UTC, datetime
from pathlib import Path

from sqlalchemy import select
from sqlalchemy.orm import Session, sessionmaker

from app.db.models import FileRecord


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


async def cleanup_loop(
    session_factory: sessionmaker[Session], interval_seconds: int = 300
) -> None:
    while True:
        await cleanup_expired_files(session_factory)
        await asyncio.sleep(interval_seconds)
