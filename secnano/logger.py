"""
Structured logging for secnano using structlog.
"""

from __future__ import annotations

import logging
import sys
from collections import deque
from collections.abc import MutableMapping
from typing import Any

import structlog

_RECENT_EVENTS: deque[dict[str, Any]] = deque(maxlen=200)


def _sanitize(value: Any) -> Any:
    if value is None or isinstance(value, (str, int, float, bool)):
        return value
    if isinstance(value, dict):
        return {str(k): _sanitize(v) for k, v in value.items()}
    if isinstance(value, (list, tuple, set)):
        return [_sanitize(v) for v in value]
    return str(value)


def _capture_recent_event(
    logger: Any,
    _: str,
    event_dict: MutableMapping[str, Any],
) -> MutableMapping[str, Any]:
    logger_name = getattr(logger, "name", None) or "secnano"
    _RECENT_EVENTS.append(
        {
            "timestamp": event_dict.get("timestamp"),
            "level": event_dict.get("level"),
            "logger": logger_name,
            "event": event_dict.get("event"),
            "fields": {
                str(key): _sanitize(value)
                for key, value in event_dict.items()
                if key not in {"timestamp", "level", "event"}
            },
        }
    )
    return event_dict


def configure_logging(level: int = logging.INFO) -> None:
    """
    Configure structlog with colored console output.

    Call this once at startup before any logging occurs.
    """
    structlog.configure(
        processors=[
            structlog.contextvars.merge_contextvars,
            structlog.processors.add_log_level,
            structlog.processors.TimeStamper(fmt="iso", utc=True),
            _capture_recent_event,
            structlog.dev.ConsoleRenderer(colors=True),
        ],
        wrapper_class=structlog.make_filtering_bound_logger(level),
        context_class=dict,
        logger_factory=structlog.PrintLoggerFactory(file=sys.stderr),
        cache_logger_on_first_use=True,
    )

    # Route stdlib logging through structlog so third-party libraries
    # also produce structured output.
    logging.basicConfig(
        format="%(message)s",
        level=level,
        handlers=[_StructlogHandler()],
        force=True,
    )


class _StructlogHandler(logging.Handler):
    """Forward stdlib log records to structlog."""

    def emit(self, record: logging.LogRecord) -> None:
        try:
            log = structlog.get_logger(record.name)
            level_method = getattr(log, record.levelname.lower(), log.info)
            level_method(self.format(record))
        except Exception:
            self.handleError(record)


def get_logger(name: str = "secnano") -> structlog.stdlib.BoundLogger:
    """Return a bound structlog logger."""
    return structlog.get_logger(name)  # type: ignore[return-value]


def get_recent_events(limit: int = 50) -> list[dict[str, Any]]:
    """Return the most recent structured log events."""
    if limit <= 0:
        return []
    return list(_RECENT_EVENTS)[-limit:]
