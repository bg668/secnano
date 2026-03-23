from __future__ import annotations

"""runtime_db: async SQLite layer (aiosqlite) for secnano task management.

All public functions are async. Callers in non-async contexts (threading,
CLI) should bridge via ``asyncio.run()``.
"""

import asyncio
import json
import uuid
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import aiosqlite

from .paths import ProjectPaths

TASK_TERMINAL_STATUSES = {"done", "failed", "cancelled", "timeout"}
TASK_ACTIVE_STATUSES = {"pending", "queued", "running"}


def utc_now_iso() -> str:
    return datetime.now(UTC).isoformat().replace("+00:00", "Z")


def create_task_id() -> str:
    return f"task_{uuid.uuid4().hex[:12]}"


@dataclass(frozen=True)
class TaskRecord:
    task_id: str
    namespace: str
    role: str
    status: str
    payload: dict[str, Any]
    result: dict[str, Any] | None
    error: str | None
    worker_id: str | None
    retry_count: int
    max_retries: int
    created_at: str
    updated_at: str
    started_at: str | None
    finished_at: str | None
    next_run_at: str | None
    schedule_type: str | None
    schedule_value: str | None
    last_run: str | None
    last_result_json: str | None

    def to_json_dict(self) -> dict[str, Any]:
        return {
            "task_id": self.task_id,
            "namespace": self.namespace,
            "role": self.role,
            "status": self.status,
            "payload": self.payload,
            "result": self.result,
            "error": self.error,
            "worker_id": self.worker_id,
            "retry_count": self.retry_count,
            "max_retries": self.max_retries,
            "created_at": self.created_at,
            "updated_at": self.updated_at,
            "started_at": self.started_at,
            "finished_at": self.finished_at,
            "next_run_at": self.next_run_at,
            "schedule_type": self.schedule_type,
            "schedule_value": self.schedule_value,
            "last_run": self.last_run,
        }


async def _connect(db_path: Path) -> aiosqlite.Connection:
    conn = await aiosqlite.connect(db_path)
    conn.row_factory = aiosqlite.Row
    await conn.execute("PRAGMA journal_mode=WAL;")
    await conn.execute("PRAGMA busy_timeout=5000;")
    return conn


_INIT_SQL = """
CREATE TABLE IF NOT EXISTS tasks (
  task_id TEXT PRIMARY KEY,
  namespace TEXT NOT NULL DEFAULT 'main',
  role TEXT,
  status TEXT NOT NULL,
  payload_json TEXT NOT NULL,
  result_json TEXT,
  error_text TEXT,
  worker_id TEXT,
  retry_count INTEGER NOT NULL DEFAULT 0,
  max_retries INTEGER NOT NULL DEFAULT 0,
  created_at TEXT NOT NULL,
  updated_at TEXT NOT NULL,
  started_at TEXT,
  finished_at TEXT,
  next_run_at TEXT,
  schedule_type TEXT,
  schedule_value TEXT,
  last_run TEXT,
  last_result_json TEXT
);

CREATE INDEX IF NOT EXISTS idx_tasks_status_created
ON tasks(status, created_at);

CREATE INDEX IF NOT EXISTS idx_tasks_next_run
ON tasks(next_run_at);

CREATE TABLE IF NOT EXISTS task_run_logs (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  task_id TEXT NOT NULL,
  attempt_no INTEGER NOT NULL,
  worker_id TEXT,
  status TEXT NOT NULL,
  duration_ms INTEGER,
  error_text TEXT,
  result_json TEXT,
  created_at TEXT NOT NULL,
  FOREIGN KEY(task_id) REFERENCES tasks(task_id)
);

CREATE UNIQUE INDEX IF NOT EXISTS idx_task_run_logs_unique_attempt
ON task_run_logs(task_id, attempt_no);
"""

# Migration: add new columns if they don't exist (for existing DBs)
_MIGRATE_COLUMNS = [
    "ALTER TABLE tasks ADD COLUMN schedule_type TEXT",
    "ALTER TABLE tasks ADD COLUMN schedule_value TEXT",
    "ALTER TABLE tasks ADD COLUMN last_run TEXT",
    "ALTER TABLE tasks ADD COLUMN last_result_json TEXT",
]


async def init_db(paths: ProjectPaths) -> None:
    """Initialise the database schema, applying any pending migrations."""
    paths.ensure_runtime_dirs()
    async with aiosqlite.connect(paths.db_path) as conn:
        conn.row_factory = aiosqlite.Row
        await conn.execute("PRAGMA journal_mode=WAL;")
        await conn.execute("PRAGMA busy_timeout=5000;")
        await conn.executescript(_INIT_SQL)
        # Apply column migrations for existing databases
        for stmt in _MIGRATE_COLUMNS:
            try:
                await conn.execute(stmt)
            except Exception:
                pass  # column already exists
        await conn.commit()


async def create_task(
    paths: ProjectPaths,
    *,
    role: str,
    task: str,
    namespace: str = "main",
    max_retries: int = 0,
    schedule_type: str | None = None,
    schedule_value: str | None = None,
    next_run_at: str | None = None,
) -> TaskRecord:
    return await create_task_with_id(
        paths,
        task_id=create_task_id(),
        role=role,
        task=task,
        namespace=namespace,
        max_retries=max_retries,
        schedule_type=schedule_type,
        schedule_value=schedule_value,
        next_run_at=next_run_at,
    )


async def create_task_with_id(
    paths: ProjectPaths,
    *,
    task_id: str,
    role: str,
    task: str,
    namespace: str = "main",
    max_retries: int = 0,
    schedule_type: str | None = None,
    schedule_value: str | None = None,
    next_run_at: str | None = None,
) -> TaskRecord:
    now = utc_now_iso()
    payload = {"task": task}
    async with aiosqlite.connect(paths.db_path) as conn:
        conn.row_factory = aiosqlite.Row
        await conn.execute("PRAGMA busy_timeout=5000;")
        await conn.execute(
            """
            INSERT OR IGNORE INTO tasks (
              task_id, namespace, role, status, payload_json, result_json, error_text, worker_id,
              retry_count, max_retries, created_at, updated_at, started_at, finished_at,
              next_run_at, schedule_type, schedule_value, last_run, last_result_json
            ) VALUES (?, ?, ?, 'pending', ?, NULL, NULL, NULL, 0, ?, ?, ?, NULL, NULL,
                      ?, ?, ?, NULL, NULL)
            """,
            (
                task_id, namespace, role,
                json.dumps(payload, ensure_ascii=False),
                max_retries, now, now,
                next_run_at, schedule_type, schedule_value,
            ),
        )
        await conn.commit()
    result = await get_task(paths, task_id)
    assert result is not None, f"Task {task_id} was not found after creation"
    return result


async def get_task(paths: ProjectPaths, task_id: str) -> TaskRecord | None:
    async with aiosqlite.connect(paths.db_path) as conn:
        conn.row_factory = aiosqlite.Row
        await conn.execute("PRAGMA busy_timeout=5000;")
        cursor = await conn.execute("SELECT * FROM tasks WHERE task_id = ?", (task_id,))
        row = await cursor.fetchone()
    if row is None:
        return None
    return _row_to_task(row)


async def list_tasks(
    paths: ProjectPaths,
    *,
    status: str | None = None,
    limit: int = 20,
) -> list[TaskRecord]:
    query = "SELECT * FROM tasks"
    params: list[Any] = []
    if status:
        query += " WHERE status = ?"
        params.append(status)
    query += " ORDER BY created_at ASC LIMIT ?"
    params.append(limit)
    async with aiosqlite.connect(paths.db_path) as conn:
        conn.row_factory = aiosqlite.Row
        await conn.execute("PRAGMA busy_timeout=5000;")
        cursor = await conn.execute(query, params)
        rows = await cursor.fetchall()
    return [_row_to_task(row) for row in rows]


def _row_to_task(row: aiosqlite.Row) -> TaskRecord:
    keys = row.keys()
    return TaskRecord(
        task_id=row["task_id"],
        namespace=row["namespace"],
        role=row["role"],
        status=row["status"],
        payload=json.loads(row["payload_json"]),
        result=json.loads(row["result_json"]) if row["result_json"] else None,
        error=row["error_text"],
        worker_id=row["worker_id"],
        retry_count=row["retry_count"],
        max_retries=row["max_retries"],
        created_at=row["created_at"],
        updated_at=row["updated_at"],
        started_at=row["started_at"],
        finished_at=row["finished_at"],
        next_run_at=row["next_run_at"],
        schedule_type=row["schedule_type"] if "schedule_type" in keys else None,
        schedule_value=row["schedule_value"] if "schedule_value" in keys else None,
        last_run=row["last_run"] if "last_run" in keys else None,
        last_result_json=row["last_result_json"] if "last_result_json" in keys else None,
    )


async def claim_task(paths: ProjectPaths, task_id: str, worker_id: str) -> bool:
    """Atomically claim a pending/queued task. Returns True if successful."""
    now = utc_now_iso()
    async with aiosqlite.connect(paths.db_path) as conn:
        await conn.execute("PRAGMA busy_timeout=5000;")
        cursor = await conn.execute(
            """
            UPDATE tasks
            SET status = 'claimed', worker_id = ?, updated_at = ?
            WHERE task_id = ? AND status IN ('pending', 'queued')
            """,
            (worker_id, now, task_id),
        )
        await conn.commit()
        return cursor.rowcount == 1


async def mark_running(paths: ProjectPaths, task_id: str, worker_id: str) -> None:
    """Mark a task as running."""
    now = utc_now_iso()
    async with aiosqlite.connect(paths.db_path) as conn:
        await conn.execute("PRAGMA busy_timeout=5000;")
        await conn.execute(
            """
            UPDATE tasks
            SET status = 'running', worker_id = ?, started_at = ?, updated_at = ?
            WHERE task_id = ?
            """,
            (worker_id, now, now, task_id),
        )
        await conn.commit()


async def mark_done(paths: ProjectPaths, task_id: str, result: dict) -> None:
    """Mark a task as done with result."""
    now = utc_now_iso()
    async with aiosqlite.connect(paths.db_path) as conn:
        await conn.execute("PRAGMA busy_timeout=5000;")
        await conn.execute(
            """
            UPDATE tasks
            SET status = 'done', result_json = ?, finished_at = ?, updated_at = ?
            WHERE task_id = ?
            """,
            (json.dumps(result, ensure_ascii=False), now, now, task_id),
        )
        await conn.commit()


async def mark_failed(paths: ProjectPaths, task_id: str, error: str) -> None:
    """Mark a task as failed with error text."""
    now = utc_now_iso()
    async with aiosqlite.connect(paths.db_path) as conn:
        await conn.execute("PRAGMA busy_timeout=5000;")
        await conn.execute(
            """
            UPDATE tasks
            SET status = 'failed', error_text = ?, finished_at = ?, updated_at = ?
            WHERE task_id = ?
            """,
            (error, now, now, task_id),
        )
        await conn.commit()


async def mark_timeout(paths: ProjectPaths, task_id: str, error_detail: dict) -> None:
    """Mark a task as timed out, recording pid/duration/last_output in error_text."""
    now = utc_now_iso()
    error_json = json.dumps(error_detail, ensure_ascii=False)
    async with aiosqlite.connect(paths.db_path) as conn:
        await conn.execute("PRAGMA busy_timeout=5000;")
        await conn.execute(
            """
            UPDATE tasks
            SET status = 'timeout', error_text = ?, finished_at = ?, updated_at = ?
            WHERE task_id = ?
            """,
            (error_json, now, now, task_id),
        )
        await conn.commit()


async def mark_paused(paths: ProjectPaths, task_id: str) -> None:
    """Mark a task as paused."""
    now = utc_now_iso()
    async with aiosqlite.connect(paths.db_path) as conn:
        await conn.execute("PRAGMA busy_timeout=5000;")
        await conn.execute(
            "UPDATE tasks SET status = 'paused', updated_at = ? WHERE task_id = ?",
            (now, task_id),
        )
        await conn.commit()


async def mark_resumed(paths: ProjectPaths, task_id: str) -> None:
    """Resume a paused task by resetting it to pending."""
    now = utc_now_iso()
    async with aiosqlite.connect(paths.db_path) as conn:
        await conn.execute("PRAGMA busy_timeout=5000;")
        await conn.execute(
            "UPDATE tasks SET status = 'pending', updated_at = ? WHERE task_id = ?",
            (now, task_id),
        )
        await conn.commit()


async def mark_cancelled(paths: ProjectPaths, task_id: str) -> None:
    """Cancel a task."""
    now = utc_now_iso()
    async with aiosqlite.connect(paths.db_path) as conn:
        await conn.execute("PRAGMA busy_timeout=5000;")
        await conn.execute(
            "UPDATE tasks SET status = 'cancelled', updated_at = ? WHERE task_id = ?",
            (now, task_id),
        )
        await conn.commit()


async def get_due_tasks(paths: ProjectPaths, now: datetime) -> list[TaskRecord]:
    """Return scheduled tasks whose next_run_at is at or before *now*."""
    now_iso = now.isoformat().replace("+00:00", "Z")
    async with aiosqlite.connect(paths.db_path) as conn:
        conn.row_factory = aiosqlite.Row
        await conn.execute("PRAGMA busy_timeout=5000;")
        cursor = await conn.execute(
            """
            SELECT * FROM tasks
            WHERE next_run_at IS NOT NULL
              AND next_run_at <= ?
              AND status IN ('pending', 'active', 'paused')
              AND schedule_type IS NOT NULL
            ORDER BY next_run_at ASC
            """,
            (now_iso,),
        )
        rows = await cursor.fetchall()
    return [_row_to_task(row) for row in rows]


async def update_schedule_after_run(
    paths: ProjectPaths,
    task_id: str,
    next_run: str | None,
) -> None:
    """Update last_run and next_run_at after a scheduled task fires."""
    now = utc_now_iso()
    async with aiosqlite.connect(paths.db_path) as conn:
        await conn.execute("PRAGMA busy_timeout=5000;")
        await conn.execute(
            """
            UPDATE tasks
            SET last_run = ?, next_run_at = ?, updated_at = ?
            WHERE task_id = ?
            """,
            (now, next_run, now, task_id),
        )
        await conn.commit()


async def append_run_log(
    paths: ProjectPaths,
    task_id: str,
    attempt_no: int,
    worker_id: str | None,
    status: str,
    duration_ms: int | None,
    error_text: str | None,
    result: dict | None,
) -> None:
    """Append an entry to task_run_logs."""
    now = utc_now_iso()
    result_json = json.dumps(result, ensure_ascii=False) if result is not None else None
    async with aiosqlite.connect(paths.db_path) as conn:
        await conn.execute("PRAGMA busy_timeout=5000;")
        await conn.execute(
            """
            INSERT OR REPLACE INTO task_run_logs
              (task_id, attempt_no, worker_id, status, duration_ms, error_text, result_json, created_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (task_id, attempt_no, worker_id, status, duration_ms, error_text, result_json, now),
        )
        await conn.commit()


async def get_run_logs(paths: ProjectPaths, task_id: str) -> list[dict[str, Any]]:
    """Return all run log entries for a task, ordered by attempt_no."""
    async with aiosqlite.connect(paths.db_path) as conn:
        conn.row_factory = aiosqlite.Row
        await conn.execute("PRAGMA busy_timeout=5000;")
        cursor = await conn.execute(
            """
            SELECT * FROM task_run_logs
            WHERE task_id = ?
            ORDER BY attempt_no ASC
            """,
            (task_id,),
        )
        rows = await cursor.fetchall()
    return [dict(row) for row in rows]


async def list_pending_tasks(paths: ProjectPaths, limit: int = 10) -> list[TaskRecord]:
    """Return pending/queued tasks ordered by creation time."""
    async with aiosqlite.connect(paths.db_path) as conn:
        conn.row_factory = aiosqlite.Row
        await conn.execute("PRAGMA busy_timeout=5000;")
        cursor = await conn.execute(
            """
            SELECT * FROM tasks
            WHERE status IN ('pending', 'queued')
            ORDER BY created_at ASC
            LIMIT ?
            """,
            (limit,),
        )
        rows = await cursor.fetchall()
    return [_row_to_task(row) for row in rows]


async def update_task_status(paths: ProjectPaths, task_id: str, status: str) -> None:
    """Generic status update (e.g. for queued or other intermediate states)."""
    now = utc_now_iso()
    async with aiosqlite.connect(paths.db_path) as conn:
        await conn.execute("PRAGMA busy_timeout=5000;")
        await conn.execute(
            "UPDATE tasks SET status = ?, updated_at = ? WHERE task_id = ?",
            (status, now, task_id),
        )
        await conn.commit()
