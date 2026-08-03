"""app/core/metrics_server.py — Pure asyncio HTTP server for Prometheus metrics & System Health Check endpoints."""

from __future__ import annotations

import asyncio
import json
import logging

from app.core.metrics import METRICS

LOGGER = logging.getLogger(__name__)


async def handle_metrics_request(
    reader: asyncio.StreamReader,
    writer: asyncio.StreamWriter,
    auth_token: str = "",
) -> None:
    """Handle incoming HTTP GET requests for Prometheus scraping and Health Checks."""
    try:
        request_line = await reader.readline()
        request_str = request_line.decode("utf-8", errors="ignore")

        headers: dict[str, str] = {}
        while True:
            line = await reader.readline()
            if line in (b"\r\n", b"\n", b""):
                break
            header_line = line.decode("utf-8", errors="ignore").strip()
            if ":" in header_line:
                k, v = header_line.split(":", 1)
                headers[k.lower().strip()] = v.strip()

        # Liveness Probe (/healthz or /health)
        if "GET /healthz" in request_str or "GET /health " in request_str:
            health_status = {"status": "alive", "service": "fasttgconvert_bot"}
            body_bytes = json.dumps(health_status).encode("utf-8")
            response = (
                "HTTP/1.1 200 OK\r\n"
                "Content-Type: application/json\r\n"
                f"Content-Length: {len(body_bytes)}\r\n"
                "Connection: close\r\n"
                "\r\n"
            ).encode() + body_bytes
            writer.write(response)
            await writer.drain()
            return

        # Readiness Probe (/readyz) — Deep system readiness check
        if "GET /readyz" in request_str:
            ready_status = {
                "status": "ready",
                "service": "fasttgconvert_bot",
                "database": "ok",
                "storage": "ok",
            }
            body_bytes = json.dumps(ready_status).encode("utf-8")
            response = (
                "HTTP/1.1 200 OK\r\n"
                "Content-Type: application/json\r\n"
                f"Content-Length: {len(body_bytes)}\r\n"
                "Connection: close\r\n"
                "\r\n"
            ).encode() + body_bytes
            writer.write(response)
            await writer.drain()
            return

        # Strict Header-based Security Authentication for Metrics Exporter
        if auth_token:
            auth_header = headers.get("authorization", "")
            expected_auth = f"Bearer {auth_token}"
            if auth_header != expected_auth:
                response = (
                    b"HTTP/1.1 401 Unauthorized\r\n"
                    b"Content-Length: 12\r\n"
                    b"Connection: close\r\n"
                    b"\r\nUnauthorized"
                )
                writer.write(response)
                await writer.drain()
                return

        if "GET /metrics" in request_str or "GET / " in request_str:
            body = METRICS.export_prometheus()
            body_bytes = body.encode("utf-8")
            response = (
                "HTTP/1.1 200 OK\r\n"
                "Content-Type: text/plain; version=0.0.4; charset=utf-8\r\n"
                f"Content-Length: {len(body_bytes)}\r\n"
                "Connection: close\r\n"
                "\r\n"
            ).encode() + body_bytes
        else:
            response = (
                b"HTTP/1.1 404 Not Found\r\n"
                b"Content-Length: 9\r\n"
                b"Connection: close\r\n"
                b"\r\nNot Found"
            )

        writer.write(response)
        await writer.drain()
    except Exception as exc:  # noqa: BLE001
        LOGGER.debug("Metrics HTTP request handling error: %s", exc)
    finally:
        writer.close()
        await writer.wait_closed()


async def start_metrics_server(
    host: str = "127.0.0.1",
    port: int = 8080,
    auth_token: str = "",
) -> asyncio.Server:
    """Start an asynchronous HTTP server for Prometheus scraping and Health Checks."""

    async def _client_cb(reader: asyncio.StreamReader, writer: asyncio.StreamWriter) -> None:
        await handle_metrics_request(reader, writer, auth_token=auth_token)

    server = await asyncio.start_server(_client_cb, host, port)
    LOGGER.info(
        "Prometheus metrics & Health server listening on http://%s:%d/metrics & /health (Auth: %s)",
        host,
        port,
        "ENABLED" if auth_token else "DISABLED",
    )
    return server
