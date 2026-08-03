"""tests/test_observability.py — Unit tests for structured logging and task tracing middleware."""

import asyncio
import json
import logging
from io import StringIO
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock

import pytest
from aiogram.types import Message, User

from app.core import (
    StructuredJSONFormatter,
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
from app.middlewares import TracingMiddleware


def test_tracing_context_management() -> None:
    clear_tracing_context()
    assert get_trace_id() is None
    assert get_user_id() is None
    assert get_service_name() is None

    tid = set_trace_id("test_trace_123")
    assert get_trace_id() == "test_trace_123"
    assert tid == "test_trace_123"

    set_user_id(99999)
    assert get_user_id() == 99999

    set_service_name("account_age")
    assert get_service_name() == "account_age"

    clear_tracing_context()
    assert get_trace_id() is None
    assert get_user_id() is None
    assert get_service_name() is None


def test_trace_scope_sync_context_manager() -> None:
    clear_tracing_context()
    with trace_scope(user_id=12345, service_name="privacy_check") as tid:
        assert len(tid) == 8
        assert get_trace_id() == tid
        assert get_user_id() == 12345
        assert get_service_name() == "privacy_check"

    assert get_trace_id() is None
    assert get_user_id() is None
    assert get_service_name() is None


@pytest.mark.asyncio
async def test_trace_scope_async_context_manager() -> None:
    clear_tracing_context()
    async with async_trace_scope(user_id=67890, service_name="otp_reader") as tid:
        assert len(tid) == 8
        assert get_trace_id() == tid
        assert get_user_id() == 67890
        assert get_service_name() == "otp_reader"

    assert get_trace_id() is None
    assert get_user_id() is None
    assert get_service_name() is None


def test_structured_json_formatter() -> None:
    stream = StringIO()
    handler = logging.StreamHandler(stream)
    handler.setFormatter(StructuredJSONFormatter())

    logger = logging.getLogger("test_json_logger")
    logger.addHandler(handler)
    logger.setLevel(logging.INFO)

    with trace_scope(user_id=44444, service_name="clean_chat") as tid:
        logger.info("Processing clean chat request", extra={"duration_ms": 145.67})

    output = stream.getvalue().strip()
    data = json.loads(output)

    assert data["level"] == "INFO"
    assert data["logger"] == "test_json_logger"
    assert data["message"] == "Processing clean chat request"
    assert data["trace_id"] == tid
    assert data["user_id"] == 44444
    assert data["service"] == "clean_chat"
    assert data["duration_ms"] == 145.67
    assert "timestamp" in data


@pytest.mark.asyncio
async def test_tracing_middleware_success() -> None:
    middleware = TracingMiddleware()
    handler_mock = AsyncMock(return_value="OK")

    event = MagicMock(spec=Message)
    user_mock = MagicMock(spec=User)
    user_mock.id = 88888
    event.from_user = user_mock

    res = await middleware(handler_mock, event, {})

    assert res == "OK"
    assert handler_mock.called


def test_mask_sensitive_data() -> None:
    from app.core import mask_sensitive_data

    raw = "Connecting to socks5://myuser:supersecretpass@1.2.3.4:1080 with bot_token=123:ABC"
    masked = mask_sensitive_data(raw)
    assert "supersecretpass" not in masked
    assert "socks5://myuser:***MASKED***@1.2.3.4:1080" in masked
    assert "bot_token=***MASKED***" in masked


def test_metrics_collector() -> None:
    from app.core import MetricsCollector

    collector = MetricsCollector()
    collector.inc_counter("telegram_tasks_total", labels={"status": "success"})
    collector.set_gauge("active_tasks", 3)
    collector.observe_histogram("task_duration_seconds", 1.25)

    prom_text = collector.export_prometheus()
    assert "# TYPE telegram_tasks_total counter" in prom_text
    assert 'telegram_tasks_total{status="success"} 1.0' in prom_text
    assert "# TYPE active_tasks gauge" in prom_text
    assert "active_tasks 3" in prom_text
    assert "# TYPE task_duration_seconds summary" in prom_text
    assert "task_duration_seconds_count 1" in prom_text


@pytest.mark.asyncio
async def test_metrics_http_server() -> None:
    import urllib.request

    from app.core import METRICS
    from app.core.metrics_server import start_metrics_server

    METRICS.inc_counter("test_http_counter")
    server = await start_metrics_server(host="127.0.0.1", port=18080)

    def fetch_metrics() -> str:
        with urllib.request.urlopen("http://127.0.0.1:18080/metrics", timeout=2) as req:
            return req.read().decode("utf-8")

    try:
        content = await asyncio.to_thread(fetch_metrics)
        assert "test_http_counter" in content
    finally:
        server.close()
        await server.wait_closed()


@pytest.mark.asyncio
async def test_metrics_http_server_authentication() -> None:
    import urllib.error
    import urllib.request

    from app.core import METRICS
    from app.core.metrics_server import start_metrics_server

    METRICS.inc_counter("test_auth_counter")
    server = await start_metrics_server(
        host="127.0.0.1", port=18081, auth_token="secret_token_123"
    )

    def fetch_unauthorized() -> int:
        try:
            with urllib.request.urlopen("http://127.0.0.1:18081/metrics", timeout=2) as req:
                return req.status
        except urllib.error.HTTPError as exc:
            return exc.code

    def fetch_authorized() -> str:
        req = urllib.request.Request("http://127.0.0.1:18081/metrics")
        req.add_header("Authorization", "Bearer secret_token_123")
        with urllib.request.urlopen(req, timeout=2) as resp:
            return resp.read().decode("utf-8")

    try:
        status_unauth = await asyncio.to_thread(fetch_unauthorized)
        assert status_unauth == 401

        content_auth = await asyncio.to_thread(fetch_authorized)
        assert "test_auth_counter" in content_auth
    finally:
        server.close()
        await server.wait_closed()


@pytest.mark.asyncio
async def test_health_check_endpoint() -> None:
    import urllib.request

    from app.core.metrics_server import start_metrics_server

    server = await start_metrics_server(
        host="127.0.0.1", port=18082, auth_token="secret_token_123"
    )

    def fetch_health() -> str:
        with urllib.request.urlopen("http://127.0.0.1:18082/healthz", timeout=2) as resp:
            return resp.read().decode("utf-8")

    def fetch_ready() -> str:
        with urllib.request.urlopen("http://127.0.0.1:18082/readyz", timeout=2) as resp:
            return resp.read().decode("utf-8")

    try:
        content_health = await asyncio.to_thread(fetch_health)
        data_health = json.loads(content_health)
        assert data_health["status"] == "alive"

        content_ready = await asyncio.to_thread(fetch_ready)
        data_ready = json.loads(content_ready)
        assert data_ready["status"] == "ready"
    finally:
        server.close()
        await server.wait_closed()


def test_perform_database_backup(tmp_path: Path) -> None:
    import sqlite3

    from app.db.backup import perform_database_backup, restore_database_backup

    db_dir = tmp_path / "db"
    db_dir.mkdir(parents=True, exist_ok=True)
    db_file = db_dir / "test.db"
    restored_db_file = db_dir / "restored.db"
    backup_dir = db_dir / "backups"

    conn = sqlite3.connect(db_file)
    conn.execute("CREATE TABLE test (id INT, val TEXT);")
    conn.execute("INSERT INTO test VALUES (1, 'hello_backup');")
    conn.commit()
    conn.close()

    b1 = perform_database_backup(db_file, backup_dir=backup_dir, max_backups=2)
    assert b1 is not None and b1.exists()

    # Test Restore
    ok = restore_database_backup(b1, restored_db_file)
    assert ok is True

    r_conn = sqlite3.connect(restored_db_file)
    cursor = r_conn.execute("SELECT val FROM test WHERE id = 1;")
    row = cursor.fetchone()
    r_conn.close()
    assert row is not None and row[0] == "hello_backup"


@pytest.mark.asyncio
async def test_retry_async_success() -> None:
    from app.core.retry import retry_async

    attempts = 0

    async def flaky_op() -> str:
        nonlocal attempts
        attempts += 1
        if attempts < 2:
            raise TimeoutError("Temporary network timeout")
        return "SUCCESS"

    res = await retry_async(flaky_op, retries=3, initial_delay=0.01)
    assert res == "SUCCESS"
    assert attempts == 2
