"""app/core/logging.py — Structured JSON log formatter with PII redaction and RotatingFileHandler."""

from __future__ import annotations

import json
import logging
import re
import sys
from datetime import UTC, datetime
from logging.handlers import RotatingFileHandler
from pathlib import Path
from typing import Any

from app.core.tracing import get_service_name, get_trace_id, get_user_id


def mask_sensitive_data(text: str) -> str:
    """Mask credentials, tokens, and sensitive URL passwords in log outputs."""
    if not text:
        return text
    # Mask proxy passwords in connection URLs: e.g. socks5://user:pass@host:port -> socks5://user:***MASKED***@host:port
    masked = re.sub(
        r"(?i)(socks5|socks4|http|https)://([^:]+):([^@]+)@",
        r"\1://\2:***MASKED***@",
        text,
    )
    # Mask parameter key-value secrets
    masked = re.sub(
        r"(?i)(password|pass|secret|bot_token|api_hash)=['\"]?[^'\s\"&]+['\"]?",
        r"\1=***MASKED***",
        masked,
    )
    return masked


class StructuredJSONFormatter(logging.Formatter):
    """Custom JSON formatter embedding contextual tracing variables and redacting sensitive PII."""

    def format(self, record: logging.LogRecord) -> str:
        raw_msg = record.getMessage()
        masked_msg = mask_sensitive_data(raw_msg)

        log_payload: dict[str, Any] = {
            "timestamp": datetime.fromtimestamp(record.created, tz=UTC).isoformat(),
            "level": record.levelname,
            "logger": record.name,
            "message": masked_msg,
            "trace_id": get_trace_id(),
            "user_id": get_user_id(),
            "service": get_service_name(),
        }

        # Include duration_ms if passed via extra={"duration_ms": ...}
        duration_ms = getattr(record, "duration_ms", None)
        if duration_ms is not None:
            log_payload["duration_ms"] = round(float(duration_ms), 2)

        # Include exception details if present (with PII masking)
        if record.exc_info:
            log_payload["exception"] = mask_sensitive_data(
                self.formatException(record.exc_info)
            )

        return json.dumps(log_payload, ensure_ascii=False)


def setup_logging(
    log_level: str = "INFO",
    json_format: bool = True,
    log_dir: Path | str | None = "logs",
) -> None:
    """Configure global application logging with stdout and RotatingFileHandler."""
    level = getattr(logging, log_level.upper(), logging.INFO)
    root_logger = logging.getLogger()
    root_logger.setLevel(level)

    # Clear pre-existing handlers
    for handler in root_logger.handlers[:]:
        root_logger.removeHandler(handler)

    formatter = (
        StructuredJSONFormatter()
        if json_format
        else logging.Formatter(
            "%(asctime)s %(levelname)s [%(name)s] trace_id=%(trace_id)s user_id=%(user_id)s: %(message)s"
        )
    )

    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setLevel(level)
    console_handler.setFormatter(formatter)
    root_logger.addHandler(console_handler)

    if log_dir:
        log_path = Path(log_dir)
        log_path.mkdir(parents=True, exist_ok=True)
        file_handler = RotatingFileHandler(
            log_path / "app.log",
            maxBytes=10 * 1024 * 1024,  # 10 MB
            backupCount=5,
            encoding="utf-8",
        )
        file_handler.setLevel(level)
        file_handler.setFormatter(formatter)
        root_logger.addHandler(file_handler)
