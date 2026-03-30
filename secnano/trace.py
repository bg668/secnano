"""
Trace event storage for host flow assertions and replay.
"""

from __future__ import annotations

from collections import deque

from secnano.db import insert_trace_event
from secnano.types import TraceEvent


class TraceStore:
    """Keep a bounded in-memory trace buffer and persist every event to SQLite."""

    def __init__(self, buffer_size: int = 200) -> None:
        self._recent: deque[TraceEvent] = deque(maxlen=buffer_size)

    def record(self, event: TraceEvent) -> None:
        self._recent.append(event)
        insert_trace_event(event)

    def list_recent(self, limit: int | None = None) -> list[TraceEvent]:
        events = list(self._recent)
        if limit is None or limit >= len(events):
            return events
        return events[-limit:]


_default_trace_store = TraceStore()


def get_trace_store() -> TraceStore:
    """Return the process-wide trace store used by host components."""
    return _default_trace_store
