"""
Structured logging for secnano using structlog.
"""

from __future__ import annotations

import logging
import sys

import structlog


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
        stream=sys.stderr,
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
