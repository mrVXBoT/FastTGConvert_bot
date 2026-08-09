"""app/services/broadcast.py — Persistent Async Queue & Worker Architecture for Broadcast messaging."""

from __future__ import annotations

import asyncio
import logging
from dataclasses import dataclass, field
from typing import Any
from uuid import uuid4

from aiogram import Bot
from aiogram.exceptions import TelegramRetryAfter, TelegramUnauthorizedError
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db.models import User
from app.db.repositories import (
    get_pending_broadcast_job_records,
    save_broadcast_job_record,
    update_broadcast_job_progress,
)
from app.services.mass_message import ProcessRateLimiter

LOGGER = logging.getLogger(__name__)

# How many parallel senders one broadcast job may run. The global limiter
# (0.04s pacing) keeps the bot at ~25 msg/s regardless of the pool size.
_BROADCAST_WORKER_COUNT = 8


@dataclass
class BroadcastJob:
    job_id: str
    message_type: str  # 'forward' or 'custom'
    from_chat_id: int | None = None
    message_id: int | None = None
    text: str | None = None
    photo: str | None = None
    video: str | None = None
    document: str | None = None
    reply_markup: Any = None
    status: str = "pending"  # pending, running, completed, cancelled, paused
    total_users: int = 0
    sent_count: int = 0
    failed_count: int = 0
    current_index: int = 0
    failed_user_ids: list[int] = field(default_factory=list)
    cancel_requested: bool = False
    admin_role: str = "ADMIN"


class BroadcastQueueWorker:
    """Persistent Async Worker Queue managing broadcast dispatch, progress tracking, cancellation and retries."""

    def __init__(self) -> None:
        self._jobs: dict[str, BroadcastJob] = {}

    def create_job(
        self,
        session: Session,
        message_type: str,
        from_chat_id: int | None = None,
        message_id: int | None = None,
        text: str | None = None,
        photo: str | None = None,
        video: str | None = None,
        document: str | None = None,
        reply_markup: Any = None,
    ) -> BroadcastJob:
        job_id = uuid4().hex[:12]
        job = BroadcastJob(
            job_id=job_id,
            message_type=message_type,
            from_chat_id=from_chat_id,
            message_id=message_id,
            text=text,
            photo=photo,
            video=video,
            document=document,
            reply_markup=reply_markup,
        )
        self._jobs[job_id] = job

        save_broadcast_job_record(
            session=session,
            job_id=job_id,
            message_type=message_type,
            from_chat_id=from_chat_id,
            message_id=message_id,
            text=text,
            photo=photo,
            video=video,
            document=document,
            status="pending",
        )
        return job

    def cancel_job(self, session: Session, job_id: str) -> bool:
        job = self._jobs.get(job_id)
        if job:
            job.cancel_requested = True
            job.status = "cancelled"

        update_broadcast_job_progress(
            session=session,
            job_id=job_id,
            sent_count=job.sent_count if job else 0,
            failed_count=job.failed_count if job else 0,
            current_index=job.current_index if job else 0,
            status="cancelled",
        )
        return True

    def get_job(self, job_id: str) -> BroadcastJob | None:
        return self._jobs.get(job_id)

    async def restore_unprocessed_jobs(self, session: Session) -> list[BroadcastJob]:
        """Restore pending/running jobs from DB upon system restart."""
        records = get_pending_broadcast_job_records(session)
        restored: list[BroadcastJob] = []
        for rec in records:
            job = BroadcastJob(
                job_id=rec.id,
                message_type=rec.message_type,
                from_chat_id=rec.from_chat_id,
                message_id=rec.message_id,
                text=rec.text,
                photo=rec.photo,
                video=rec.video,
                document=rec.document,
                status=rec.status,
                total_users=rec.total_users,
                sent_count=rec.sent_count,
                failed_count=rec.failed_count,
                current_index=rec.current_index,
            )
            self._jobs[job.job_id] = job
            restored.append(job)
        if restored:
            LOGGER.info("Restored %d unfinished broadcast jobs from database.", len(restored))
        return restored

    async def enqueue_and_process(self, bot: Bot, session: Session, job: BroadcastJob) -> BroadcastJob:
        """Enqueue job and execute processing via persistent async worker pipeline."""
        users = list(session.scalars(select(User).where(User.status == "active")).all())
        job.total_users = len(users)
        job.status = "running"

        save_broadcast_job_record(
            session=session,
            job_id=job.job_id,
            message_type=job.message_type,
            from_chat_id=job.from_chat_id,
            message_id=job.message_id,
            text=job.text,
            photo=job.photo,
            video=job.video,
            document=job.document,
            total_users=job.total_users,
            status="running",
        )

        LOGGER.info("Worker starting broadcast job %s to %d active users...", job.job_id, job.total_users)

        # Resume from current_index if restarted
        users_to_process = users[job.current_index :]

        # Bounded worker pool with a global pacing limiter. Sequential sends
        # are latency-bound (~2-5 msg/s); the pool raises throughput toward the
        # shared limiter ceiling (25 msg/s) while keeping bot API flood-safe.
        limiter = ProcessRateLimiter(min_interval_seconds=0.04)
        work_queue: asyncio.Queue[tuple[int, Any]] = asyncio.Queue()
        for idx, user in enumerate(users_to_process, start=job.current_index):
            work_queue.put_nowait((idx, user))

        # Resume-safety: current_index must stay the longest *contiguous*
        # completed prefix, even though workers finish out of order.
        attempted: set[int] = set()
        completed_prefix = job.current_index
        last_persist_prefix = job.current_index
        state_lock = asyncio.Lock()

        async def broadcast_worker() -> None:
            nonlocal completed_prefix, last_persist_prefix
            while not job.cancel_requested:
                try:
                    idx, user = work_queue.get_nowait()
                except asyncio.QueueEmpty:
                    return
                await limiter.acquire()

                try:
                    if job.message_type == "forward" and job.from_chat_id and job.message_id:
                        await bot.forward_message(
                            chat_id=user.telegram_id,
                            from_chat_id=job.from_chat_id,
                            message_id=job.message_id,
                        )
                    elif job.photo:
                        await bot.send_photo(
                            chat_id=user.telegram_id,
                            photo=job.photo,
                            caption=job.text,
                            reply_markup=job.reply_markup,
                        )
                    elif job.video:
                        await bot.send_video(
                            chat_id=user.telegram_id,
                            video=job.video,
                            caption=job.text,
                            reply_markup=job.reply_markup,
                        )
                    elif job.document:
                        await bot.send_document(
                            chat_id=user.telegram_id,
                            document=job.document,
                            caption=job.text,
                            reply_markup=job.reply_markup,
                        )
                    elif job.text:
                        await bot.send_message(
                            chat_id=user.telegram_id,
                            text=job.text,
                            reply_markup=job.reply_markup,
                        )
                    job.sent_count += 1
                except TelegramRetryAfter as retry_err:
                    job.failed_count += 1
                    job.failed_user_ids.append(user.telegram_id)
                    await asyncio.sleep(retry_err.retry_after + 1)
                except TelegramUnauthorizedError:
                    user.status = "banned"
                    job.failed_count += 1
                    job.failed_user_ids.append(user.telegram_id)
                except Exception as exc:  # noqa: BLE001
                    LOGGER.debug("Broadcast to %d failed: %s", user.telegram_id, exc)
                    job.failed_count += 1
                    job.failed_user_ids.append(user.telegram_id)

                async with state_lock:
                    attempted.add(idx)
                    while completed_prefix in attempted:
                        attempted.discard(completed_prefix)
                        completed_prefix += 1
                    job.current_index = completed_prefix
                    if completed_prefix - last_persist_prefix >= 10:
                        last_persist_prefix = completed_prefix
                        update_broadcast_job_progress(
                            session=session,
                            job_id=job.job_id,
                            total_users=job.total_users,
                            sent_count=job.sent_count,
                            failed_count=job.failed_count,
                            current_index=completed_prefix,
                            status="running",
                        )

        workers = [
            asyncio.create_task(broadcast_worker())
            for _ in range(min(_BROADCAST_WORKER_COUNT, len(users_to_process) or 1))
        ]
        await asyncio.gather(*workers)

        if job.cancel_requested:
            LOGGER.info("Broadcast job %s cancelled by admin.", job.job_id)
            job.status = "cancelled"
        elif job.status != "cancelled":
            job.status = "completed"

        update_broadcast_job_progress(
            session=session,
            job_id=job.job_id,
            total_users=job.total_users,
            sent_count=job.sent_count,
            failed_count=job.failed_count,
            current_index=job.total_users,
            status=job.status,
        )

        session.commit()
        LOGGER.info(
            "Broadcast job %s finished (%s). Sent: %d, Failed: %d",
            job.job_id,
            job.status,
            job.sent_count,
            job.failed_count,
        )
        return job


# Global Broadcast Worker Instance
BROADCAST_WORKER = BroadcastQueueWorker()
