"""app/core — Core logging, task tracing, and metrics package."""

from app.core.logging import StructuredJSONFormatter, mask_sensitive_data, setup_logging
from app.core.metrics import METRICS, MetricsCollector
from app.core.tracing import (
    async_trace_scope,
    clear_tracing_context,
    get_service_name,
    get_trace_id,
    get_user_id,
    set_service_name,
    set_trace_id,
    set_user_id,
    trace_scope,
)

__all__ = [
    "METRICS",
    "MetricsCollector",
    "StructuredJSONFormatter",
    "async_trace_scope",
    "clear_tracing_context",
    "get_service_name",
    "get_trace_id",
    "get_user_id",
    "mask_sensitive_data",
    "set_service_name",
    "set_trace_id",
    "set_user_id",
    "setup_logging",
    "trace_scope",
]
