"""app/core/tracing.py — ContextVar-based task tracing and Correlation ID context manager."""

from __future__ import annotations

from collections.abc import AsyncGenerator, Generator
from contextlib import asynccontextmanager, contextmanager
from contextvars import ContextVar
from uuid import uuid4

_TRACE_ID_CTX: ContextVar[str | None] = ContextVar("trace_id", default=None)
_USER_ID_CTX: ContextVar[int | None] = ContextVar("user_id", default=None)
_SERVICE_NAME_CTX: ContextVar[str | None] = ContextVar("service_name", default=None)


def generate_trace_id() -> str:
    """Generate a collision-resistant 8-character hex trace ID."""
    return uuid4().hex[:8]


def set_trace_id(trace_id: str | None = None) -> str:
    """Set the trace ID for the current async task context."""
    tid = trace_id or generate_trace_id()
    _TRACE_ID_CTX.set(tid)
    return tid


def get_trace_id() -> str | None:
    """Get the current trace ID from the async task context."""
    return _TRACE_ID_CTX.get()


def set_user_id(user_id: int | None) -> None:
    """Set the user ID for the current async task context."""
    _USER_ID_CTX.set(user_id)


def get_user_id() -> int | None:
    """Get the current user ID from the async task context."""
    return _USER_ID_CTX.get()


def set_service_name(name: str | None) -> None:
    """Set the active service name for the current async task context."""
    _SERVICE_NAME_CTX.set(name)


def get_service_name() -> str | None:
    """Get the active service name from the async task context."""
    return _SERVICE_NAME_CTX.get()


def clear_tracing_context() -> None:
    """Reset all tracing context variables."""
    _TRACE_ID_CTX.set(None)
    _USER_ID_CTX.set(None)
    _SERVICE_NAME_CTX.set(None)


@contextmanager
def trace_scope(
    user_id: int | None = None,
    service_name: str | None = None,
    trace_id: str | None = None,
) -> Generator[str, None, None]:
    """Synchronous context manager establishing a trace context scope."""
    tid = set_trace_id(trace_id)
    if user_id is not None:
        set_user_id(user_id)
    if service_name is not None:
        set_service_name(service_name)
    try:
        yield tid
    finally:
        clear_tracing_context()


@asynccontextmanager
async def async_trace_scope(
    user_id: int | None = None,
    service_name: str | None = None,
    trace_id: str | None = None,
) -> AsyncGenerator[str, None]:
    """Asynchronous context manager establishing a trace context scope."""
    tid = set_trace_id(trace_id)
    if user_id is not None:
        set_user_id(user_id)
    if service_name is not None:
        set_service_name(service_name)
    try:
        yield tid
    finally:
        clear_tracing_context()
