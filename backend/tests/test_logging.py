"""Tests for structured JSON logging: format, correlation ids, and job event fields."""

import json
import logging
from typing import Any

from app.core.logging import (
    JsonFormatter,
    correlation_id_var,
    job_logger,
    reset_correlation_id,
    set_correlation_id,
)


class CaptureHandler(logging.Handler):
    """Collect emitted records in memory for assertions."""

    def __init__(self) -> None:
        super().__init__()
        self.records: list[logging.LogRecord] = []

    def emit(self, record: logging.LogRecord) -> None:
        """Append the record to the capture list."""
        self.records.append(record)


def make_record(message: str = "hello") -> logging.LogRecord:
    """Create a log record independent of any configured handlers."""
    return logging.LogRecord(
        name="app.test",
        level=logging.INFO,
        pathname=__file__,
        lineno=1,
        msg=message,
        args=(),
        exc_info=None,
    )


def test_formatter_emits_single_line_json() -> None:
    """Each record serializes to one valid JSON object."""
    parsed = json.loads(JsonFormatter().format(make_record()))
    assert parsed["level"] == "INFO"
    assert parsed["msg"] == "hello"
    assert parsed["logger"] == "app.test"
    assert "ts" in parsed and "correlation_id" in parsed


def test_correlation_id_roundtrip() -> None:
    """set/reset binds the id to the context so request lines carry it."""
    token = set_correlation_id("req-123")
    try:
        assert json.loads(JsonFormatter().format(make_record()))["correlation_id"] == "req-123"
    finally:
        reset_correlation_id(token)
    assert correlation_id_var.get() is None


def test_event_fields_merged_into_json() -> None:
    """Custom event fields land in the JSON line alongside standard keys."""
    record = make_record()
    record.__dict__["event"] = "job_queued"
    record.__dict__["document_id"] = "doc-1"
    parsed = json.loads(JsonFormatter().format(record))
    assert parsed["event"] == "job_queued"
    assert parsed["document_id"] == "doc-1"
    assert parsed["logger"] == "app.test"


def test_job_logger_emits_structured_event() -> None:
    """Lifecycle helper records an event name and safe fields for observability."""
    capture = CaptureHandler()
    root = logging.getLogger()
    root.addHandler(capture)
    try:
        job_logger(logging.getLogger("app.worker"), "job_started", task_id="t-1")
    finally:
        root.removeHandler(capture)
    assert len(capture.records) == 1
    last: Any = capture.records[0]
    assert last.event == "job_started"
    assert last.task_id == "t-1"
