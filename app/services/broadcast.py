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

LOGGER = logging.getLogger(__name__)


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

        for idx, user in enumerate(users_to_process, start=job.current_index):
            if job.cancel_requested:
                LOGGER.info("Broadcast job %s cancelled by admin.", job.job_id)
                job.status = "cancelled"
                break

            job.current_index = idx

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
                await asyncio.sleep(0.04)
            except TelegramRetryAfter as retry_err:
                await asyncio.sleep(retry_err.retry_after + 1)
            except TelegramUnauthorizedError:
                user.status = "banned"
                job.failed_count += 1
                job.failed_user_ids.append(user.telegram_id)
            except Exception as exc:  # noqa: BLE001
                LOGGER.debug("Broadcast to %d failed: %s", user.telegram_id, exc)
                job.failed_count += 1
                job.failed_user_ids.append(user.telegram_id)

            # Persist DB progress batch every 10 users
            if idx % 10 == 0:
                update_broadcast_job_progress(
                    session=session,
                    job_id=job.job_id,
                    sent_count=job.sent_count,
                    failed_count=job.failed_count,
                    current_index=idx,
                    status="running",
                )

        if job.status != "cancelled":
            job.status = "completed"

        update_broadcast_job_progress(
            session=session,
            job_id=job.job_id,
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

    async def retry_failed_messages(self, bot: Bot, session: Session, job: BroadcastJob) -> BroadcastJob:
        """Retry dispatching to failed user list."""
        if not job.failed_user_ids:
            return job

        to_retry = list(job.failed_user_ids)
        job.failed_user_ids.clear()
        LOGGER.info("Retrying broadcast job %s for %d failed users...", job.job_id, len(to_retry))

        for telegram_id in to_retry:
            if job.cancel_requested:
                break
            try:
                if job.text:
                    await bot.send_message(chat_id=telegram_id, text=job.text)
                job.sent_count += 1
                job.failed_count = max(0, job.failed_count - 1)
                await asyncio.sleep(0.04)
            except Exception:  # noqa: BLE001
                job.failed_user_ids.append(telegram_id)

        update_broadcast_job_progress(
            session=session,
            job_id=job.job_id,
            sent_count=job.sent_count,
            failed_count=job.failed_count,
            current_index=job.total_users,
            status=job.status,
        )
        return job


# Global Broadcast Worker Instance
BROADCAST_WORKER = BroadcastQueueWorker()
