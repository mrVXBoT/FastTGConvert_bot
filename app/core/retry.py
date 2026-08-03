"""app/core/retry.py — Async retry wrapper with exponential backoff, jitter, and selective transient error filtering."""

from __future__ import annotations

import asyncio
import logging
import random
from collections.abc import Awaitable, Callable

LOGGER = logging.getLogger(__name__)

# Default transient network/timeout errors that are safe to retry
DEFAULT_RETRYABLE_EXCEPTIONS: tuple[type[BaseException], ...] = (
    TimeoutError,
    ConnectionError,
    OSError,
    asyncio.TimeoutError,
)


async def retry_async[T](
    func: Callable[[], Awaitable[T]],
    retries: int = 3,
    initial_delay: float = 1.0,
    backoff_factor: float = 2.0,
    exceptions: tuple[type[BaseException], ...] = DEFAULT_RETRYABLE_EXCEPTIONS,
) -> T:
    """Execute an async operation with exponential backoff and jitter strictly on transient failures."""
    delay = initial_delay
    last_exception: BaseException | None = None

    for attempt in range(1, retries + 1):
        try:
            return await func()
        except exceptions as exc:
            last_exception = exc
            if attempt == retries:
                LOGGER.warning(
                    "Retry limit reached (%d attempts). Reraising exception: %s",
                    retries,
                    exc,
                )
                raise
            jitter = random.uniform(0.8, 1.2)
            sleep_duration = delay * jitter
            LOGGER.info(
                "Attempt %d/%d failed with transient error '%s'. Retrying in %.2fs...",
                attempt,
                retries,
                exc,
                sleep_duration,
            )
            await asyncio.sleep(sleep_duration)
            delay *= backoff_factor

    if last_exception:
        raise last_exception
    raise RuntimeError("Unexpected retry termination")
