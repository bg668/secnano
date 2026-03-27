"""
Scheduled task execution engine.

Uses croniter for cron-expression parsing. Polls for due tasks every
SCHEDULER_POLL_INTERVAL seconds.
"""

from __future__ import annotations

import asyncio
import time
import uuid
from collections.abc import Awaitable, Callable
from datetime import UTC, datetime

from secnano.config import SCHEDULER_POLL_INTERVAL
from secnano.db import (
    insert_task_run_log,
    list_scheduled_tasks,
    update_task_last_result,
    update_task_next_run,
    upsert_scheduled_task,
)
from secnano.logger import get_logger
from secnano.types import ScheduledTask, TaskRunLog

log = get_logger("task_scheduler")

TaskRunner = Callable[[ScheduledTask], Awaitable[str | None]]
TaskEnqueue = Callable[[ScheduledTask, Callable[[], Awaitable[None]]], Awaitable[None]]

_queued_task_ids: set[str] = set()


def _now_utc() -> str:
    return datetime.now(UTC).isoformat()


def _compute_next_run(task: ScheduledTask, after: datetime | None = None) -> str | None:
    """Compute the next ISO-8601 run time for *task*."""
    now = after or datetime.now(UTC)

    if task.schedule_type == "once":
        return None  # Run once; no next run

    if task.schedule_type == "interval":
        try:
            seconds = float(task.schedule_value)
            next_dt = now.replace(tzinfo=UTC) if now.tzinfo is None else now
            from datetime import timedelta

            return (next_dt + timedelta(seconds=seconds)).isoformat()
        except ValueError:
            log.error("Invalid interval value", task_id=task.id, value=task.schedule_value)
            return None

    if task.schedule_type == "cron":
        try:
            from croniter import croniter

            itr = croniter(task.schedule_value, now)
            next_dt = itr.get_next(datetime)
            return next_dt.replace(tzinfo=UTC).isoformat()
        except Exception as exc:
            log.error("Invalid cron expression", task_id=task.id, error=str(exc))
            return None

    return None


def _is_due(task: ScheduledTask) -> bool:
    """Return True if *task* should run now."""
    if task.status != "active":
        return False
    if not task.next_run:
        return False

    try:
        next_run_dt = datetime.fromisoformat(task.next_run.replace("Z", "+00:00"))
        if next_run_dt.tzinfo is None:
            next_run_dt = next_run_dt.replace(tzinfo=UTC)
        return datetime.now(UTC) >= next_run_dt
    except ValueError:
        return False


async def _run_task(task: ScheduledTask, runner: TaskRunner) -> None:
    """Execute a single scheduled task and record the result."""
    start_ms = int(time.monotonic() * 1000)
    log.info("Running scheduled task", task_id=task.id, group=task.group_folder)

    run_at = _now_utc()
    result: str | None = None
    error: str | None = None
    status = "success"

    try:
        result = await runner(task)
        update_task_last_result(task.id, result)
    except Exception as exc:
        log.error("Scheduled task failed", task_id=task.id, error=str(exc))
        error = str(exc)
        status = "error"

    duration_ms = int(time.monotonic() * 1000) - start_ms
    log_entry = TaskRunLog(
        task_id=task.id,
        run_at=run_at,
        duration_ms=duration_ms,
        status=status,
        result=result,
        error=error,
    )
    insert_task_run_log(log_entry)

    # Compute next run
    now_dt = datetime.now(UTC)
    next_run = _compute_next_run(task, now_dt)

    new_status = task.status
    if task.schedule_type == "once":
        new_status = "completed"

    update_task_next_run(task.id, next_run, run_at)

    if new_status != task.status:
        updated = ScheduledTask(
            id=task.id,
            group_folder=task.group_folder,
            chat_jid=task.chat_jid,
            prompt=task.prompt,
            schedule_type=task.schedule_type,
            schedule_value=task.schedule_value,
            context_mode=task.context_mode,
            next_run=next_run,
            last_run=run_at,
            last_result=result,
            status=new_status,
            created_at=task.created_at,
        )
        upsert_scheduled_task(updated)


async def start_scheduler_loop(
    runner: TaskRunner,
    enqueue: TaskEnqueue | None = None,
    poll_interval: float = SCHEDULER_POLL_INTERVAL,
) -> None:
    """
    Poll the database for due scheduled tasks and run them.

    This coroutine loops forever (until cancelled).

    Args:
        runner: Async function that executes a task and returns its result string.
        poll_interval: Seconds between database polls.
    """
    log.info("Scheduler loop started", poll_interval=poll_interval)

    while True:
        try:
            await _enqueue_due_tasks_once(runner=runner, enqueue=enqueue)
        except Exception as exc:
            log.error("Scheduler loop error", error=str(exc))

        await asyncio.sleep(poll_interval)


async def _enqueue_due_tasks_once(
    runner: TaskRunner,
    enqueue: TaskEnqueue | None = None,
) -> int:
    """
    Enqueue due tasks once and return the number of newly enqueued tasks.

    When ``enqueue`` is ``None``, tasks are started as background asyncio tasks.
    """
    tasks = list_scheduled_tasks(status="active")
    due = [t for t in tasks if _is_due(t)]
    enqueued_count = 0

    for task in due:
        if task.id in _queued_task_ids:
            continue

        _queued_task_ids.add(task.id)

        async def _run_wrapped(current: ScheduledTask = task) -> None:
            try:
                await _run_task(current, runner)
            finally:
                _queued_task_ids.discard(current.id)

        try:
            if enqueue:
                await enqueue(task, _run_wrapped)
            else:
                asyncio.create_task(_run_wrapped())
        except Exception:
            _queued_task_ids.discard(task.id)
            raise
        enqueued_count += 1

    if enqueued_count:
        log.info("Enqueued due tasks", count=enqueued_count)

    return enqueued_count


def schedule_task(
    group_folder: str,
    chat_jid: str,
    prompt: str,
    schedule_type: str,
    schedule_value: str,
    context_mode: str = "group",
) -> ScheduledTask:
    """
    Create and persist a new scheduled task.

    Returns the created ``ScheduledTask``.
    """
    now = _now_utc()
    task = ScheduledTask(
        id=str(uuid.uuid4()),
        group_folder=group_folder,
        chat_jid=chat_jid,
        prompt=prompt,
        schedule_type=schedule_type,
        schedule_value=schedule_value,
        context_mode=context_mode,
        next_run=None,
        last_run=None,
        last_result=None,
        status="active",
        created_at=now,
    )
    # Compute initial next_run
    task.next_run = _compute_next_run(task)
    upsert_scheduled_task(task)
    log.info("Scheduled task created", task_id=task.id, type=schedule_type, value=schedule_value)
    return task
