"""Structured JSON logging with correlation ids; never logs PII, documents, or secrets."""

from __future__ import annotations

import json
import logging
import sys
from contextvars import ContextVar, Token
from datetime import UTC, datetime
from typing import Any

correlation_id_var: ContextVar[str | None] = ContextVar("correlation_id", default=None)
_service_name = "docintel-backend"

_STANDARD_RECORD_KEYS = frozenset(
    {
        "name",
        "msg",
        "args",
        "levelname",
        "levelno",
        "pathname",
        "filename",
        "module",
        "exc_info",
        "exc_text",
        "stack_info",
        "lineno",
        "funcName",
        "created",
        "msecs",
        "relativeCreated",
        "thread",
        "threadName",
        "processName",
        "process",
        "taskName",
        "message",
        "asctime",
    }
)


class JsonFormatter(logging.Formatter):
    """Render each log record as one JSON object on a single line."""

    def format(self, record: logging.LogRecord) -> str:
        """Return the record as a JSON line, merging safe custom event fields."""
        payload: dict[str, Any] = {
            "ts": datetime.now(UTC).isoformat(timespec="milliseconds"),
            "level": record.levelname,
            "logger": record.name,
            "msg": record.getMessage(),
            "correlation_id": correlation_id_var.get(),
            "service": _service_name,
        }
        if record.exc_info:
            payload["exception"] = record.exc_info[0].__name__ if record.exc_info[0] else "unknown"
        extras = {
            key: value
            for key, value in record.__dict__.items()
            if key not in _STANDARD_RECORD_KEYS and not key.startswith("_")
        }
        payload.update(extras)
        return json.dumps(payload, default=str, ensure_ascii=False)


def configure_logging(level: str = "INFO", service: str = "docintel-backend") -> None:
    """Install the JSON formatter on the root logger (idempotent)."""
    global _service_name
    _service_name = service
    handler = logging.StreamHandler(sys.stdout)
    handler.setFormatter(JsonFormatter())
    root = logging.getLogger()
    root.handlers.clear()
    root.addHandler(handler)
    root.setLevel(level.upper())


def set_correlation_id(value: str) -> Token[str | None]:
    """Bind a correlation id to the current context; pass the token to reset."""
    return correlation_id_var.set(value)


def reset_correlation_id(token: Token[str | None]) -> None:
    """Restore the correlation id to its previous value."""
    correlation_id_var.reset(token)


def job_logger(logger: logging.Logger, event: str, **fields: Any) -> None:
    """Log a job lifecycle event; callers must pass ids/enums only, never document text."""
    logger.info(event, extra={"event": event, **fields})
