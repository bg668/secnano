from __future__ import annotations

"""Scheduler: fires scheduled tasks (cron/interval/once) by polling the DB.

The Scheduler runs in a background thread and periodically calls
``get_due_tasks``. For each due task it:

1. Computes the *next* run time (or ``None`` for once-type tasks).
2. Creates a new *pending* task with a fresh ``task_id`` so the original
   scheduling record is preserved.
3. Updates the original task's ``last_run`` / ``next_run_at`` via
   ``update_schedule_after_run``.
4. For ``once`` tasks: marks the original record as ``done`` after firing.
"""

import asyncio
import logging
import threading
import time
from datetime import UTC, datetime, timedelta
from typing import Any

from .paths import ProjectPaths
from .runtime_db import (
    TaskRecord,
    create_task_id,
    create_task_with_id,
    get_due_tasks,
    mark_done,
    update_schedule_after_run,
    utc_now_iso,
)

logger = logging.getLogger(__name__)

_DEFAULT_POLL_INTERVAL = 10.0  # seconds


def _compute_next_run(task: TaskRecord, fired_at: datetime) -> str | None:
    """Return the ISO-format next run time, or ``None`` for once tasks."""
    schedule_type = task.schedule_type
    schedule_value = task.schedule_value

    if schedule_type == "once":
        return None

    if schedule_type == "interval":
        # schedule_value is the interval in milliseconds
        try:
            ms = float(schedule_value or "0")
        except ValueError:
            logger.warning("Invalid interval value for task %s: %r", task.task_id, schedule_value)
            return None
        next_dt = fired_at + timedelta(milliseconds=ms)
        return next_dt.isoformat().replace("+00:00", "Z")

    if schedule_type == "cron":
        try:
            from croniter import croniter  # noqa: PLC0415  # deferred to avoid hard dep at module level
        except ImportError:
            logger.error("croniter is not installed; cannot compute next cron run for task %s", task.task_id)
            return None
        try:
            it = croniter(schedule_value or "", fired_at)
            next_dt: datetime = it.get_next(datetime)
            if next_dt.tzinfo is None:
                next_dt = next_dt.replace(tzinfo=UTC)
            return next_dt.isoformat().replace("+00:00", "Z")
        except Exception as exc:
            logger.warning("Failed to compute cron next run for task %s: %s", task.task_id, exc)
            return None

    logger.warning("Unknown schedule_type %r for task %s", schedule_type, task.task_id)
    return None


class Scheduler:
    """Background scheduler that fires due tasks into the WorkerPool queue."""

    def __init__(
        self,
        paths: ProjectPaths,
        poll_interval: float = _DEFAULT_POLL_INTERVAL,
    ) -> None:
        self.paths = paths
        self.poll_interval = poll_interval
        self._stop_event = threading.Event()
        self._thread: threading.Thread | None = None

    def start(self) -> None:
        """Start the background scheduling thread."""
        self._stop_event.clear()
        self._thread = threading.Thread(
            target=self._loop,
            name="secnano-scheduler",
            daemon=True,
        )
        self._thread.start()
        logger.info("Scheduler started (poll_interval=%.1fs)", self.poll_interval)

    def stop(self) -> None:
        """Signal the scheduling thread to stop and wait for it to exit."""
        self._stop_event.set()
        if self._thread is not None:
            self._thread.join(timeout=15)
        logger.info("Scheduler stopped")

    def _loop(self) -> None:
        while not self._stop_event.is_set():
            try:
                self._tick()
            except Exception:
                logger.exception("Scheduler tick error")
            self._stop_event.wait(timeout=self.poll_interval)

    def _tick(self) -> None:
        now = datetime.now(UTC)
        due_tasks = asyncio.run(get_due_tasks(self.paths, now))
        if not due_tasks:
            return

        for task in due_tasks:
            try:
                self._fire_task(task, fired_at=now)
            except Exception:
                logger.exception("Failed to fire scheduled task %s", task.task_id)

    def _fire_task(self, task: TaskRecord, fired_at: datetime) -> None:
        """Spawn a new pending task and update the schedule record."""
        next_run = _compute_next_run(task, fired_at)

        # Create a new pending task (preserves original scheduling record)
        new_task_id = create_task_id()
        asyncio.run(
            create_task_with_id(
                self.paths,
                task_id=new_task_id,
                role=task.role,
                task=task.payload.get("task", ""),
                namespace=task.namespace,
                max_retries=task.max_retries,
            )
        )
        logger.info(
            "Scheduler fired task %s → new pending task %s (next_run=%s)",
            task.task_id,
            new_task_id,
            next_run,
        )

        # Update the scheduling record's last_run / next_run_at
        asyncio.run(update_schedule_after_run(self.paths, task.task_id, next_run))

        # For once-type tasks, mark the scheduling record as done
        if task.schedule_type == "once":
            asyncio.run(mark_done(self.paths, task.task_id, result={"fired_task_id": new_task_id}))
