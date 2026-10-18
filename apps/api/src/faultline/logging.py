"""JSON logs. Note text and credentials are not fields on these records."""

from __future__ import annotations

import json
import logging
from contextvars import ContextVar
from typing import Any

correlation_id_var: ContextVar[str] = ContextVar("correlation_id", default="")
tenant_id_var: ContextVar[str] = ContextVar("tenant_id", default="")

_LOG_FIELDS = (
    "correlation_id",
    "tenant_id",
    "event_name",
    "assertion_id",
    "source_id",
    "status_value",
)

_configured = False


class _JsonFormatter(logging.Formatter):
    def format(self, record: logging.LogRecord) -> str:
        payload: dict[str, Any] = {
            "level": record.levelname,
            "message": record.getMessage(),
            "logger": record.name,
        }
        for field in _LOG_FIELDS:
            value = getattr(record, field, None)
            if value:
                payload[field] = value
        if record.exc_info:
            payload["exc_type"] = record.exc_info[0].__name__ if record.exc_info[0] else ""
        return json.dumps(payload, default=str)


class _ContextFilter(logging.Filter):
    def filter(self, record: logging.LogRecord) -> bool:
        record.correlation_id = correlation_id_var.get()
        record.tenant_id = tenant_id_var.get()
        return True


def setup_logging(level: str) -> None:
    global _configured
    root = logging.getLogger()
    if not _configured:
        handler = logging.StreamHandler()
        handler.setFormatter(_JsonFormatter())
        handler.addFilter(_ContextFilter())
        root.handlers.clear()
        root.addHandler(handler)
        _configured = True
    root.setLevel(level.upper())


def log_event(event_name: str, **fields: object) -> None:
    logging.getLogger("faultline").info(
        event_name,
        extra={"event_name": event_name, **fields},
    )
