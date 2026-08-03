"""app/middlewares/tracing.py — Aiogram Tracing Middleware for automatic Correlation ID context injection."""

from __future__ import annotations

import logging
import time
from collections.abc import Awaitable, Callable
from typing import Any

from aiogram import BaseMiddleware
from aiogram.types import TelegramObject, User

from app.core import METRICS
from app.core.tracing import async_trace_scope, get_service_name

LOGGER = logging.getLogger(__name__)


class TracingMiddleware(BaseMiddleware):
    """Aiogram middleware populating task trace context variables and recording metrics for every incoming update."""

    async def __call__(
        self,
        handler: Callable[[TelegramObject, dict[str, Any]], Awaitable[Any]],
        event: TelegramObject,
        data: dict[str, Any],
    ) -> Any:
        event_user: User | None = getattr(event, "from_user", None)
        user_id: int | None = event_user.id if event_user else None

        start_time = time.perf_counter()
        METRICS.inc_gauge("active_tasks")
        async with async_trace_scope(user_id=user_id):
            try:
                result = await handler(event, data)
                elapsed_sec = time.perf_counter() - start_time
                elapsed_ms = elapsed_sec * 1000.0
                svc = get_service_name() or "bot_handler"
                METRICS.inc_counter("telegram_tasks_total", labels={"service": svc, "status": "success"})
                METRICS.observe_histogram("task_duration_seconds", elapsed_sec)
                LOGGER.info(
                    "Update processed successfully",
                    extra={"duration_ms": elapsed_ms},
                )
                return result
            except Exception:
                elapsed_sec = time.perf_counter() - start_time
                elapsed_ms = elapsed_sec * 1000.0
                svc = get_service_name() or "bot_handler"
                METRICS.inc_counter("telegram_tasks_total", labels={"service": svc, "status": "failure"})
                METRICS.observe_histogram("task_duration_seconds", elapsed_sec)
                LOGGER.exception(
                    "Update processing failed",
                    extra={"duration_ms": elapsed_ms},
                )
                raise
            finally:
                METRICS.dec_gauge("active_tasks")
