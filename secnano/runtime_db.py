from __future__ import annotations

import json
import sqlite3
import uuid
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from .paths import ProjectPaths

TASK_TERMINAL_STATUSES = {"done", "failed", "cancelled"}


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
        }


def _connect(db_path: Path) -> sqlite3.Connection:
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL;")
    conn.execute("PRAGMA busy_timeout=5000;")
    return conn


def init_db(paths: ProjectPaths) -> None:
    paths.ensure_runtime_dirs()
    with _connect(paths.db_path) as conn:
        conn.executescript(
            """
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
              next_run_at TEXT
            );

            CREATE INDEX IF NOT EXISTS idx_tasks_status_created
            ON tasks(status, created_at);

            CREATE INDEX IF NOT EXISTS idx_tasks_next_run
            ON tasks(next_run_at);
            """
        )
        conn.commit()


def create_task(
    paths: ProjectPaths,
    *,
    role: str,
    task: str,
    namespace: str = "main",
    max_retries: int = 0,
) -> TaskRecord:
    return create_task_with_id(
        paths,
        task_id=create_task_id(),
        role=role,
        task=task,
        namespace=namespace,
        max_retries=max_retries,
    )


def create_task_with_id(
    paths: ProjectPaths,
    *,
    task_id: str,
    role: str,
    task: str,
    namespace: str = "main",
    max_retries: int = 0,
) -> TaskRecord:
    now = utc_now_iso()
    payload = {"task": task}
    with _connect(paths.db_path) as conn:
        conn.execute(
            """
            INSERT OR IGNORE INTO tasks (
              task_id, namespace, role, status, payload_json, result_json, error_text, worker_id,
              retry_count, max_retries, created_at, updated_at, started_at, finished_at, next_run_at
            ) VALUES (?, ?, ?, 'pending', ?, NULL, NULL, NULL, 0, ?, ?, ?, NULL, NULL, NULL)
            """,
            (task_id, namespace, role, json.dumps(payload, ensure_ascii=False), max_retries, now, now),
        )
        conn.commit()
    return get_task(paths, task_id)


def get_task(paths: ProjectPaths, task_id: str) -> TaskRecord | None:
    with _connect(paths.db_path) as conn:
        row = conn.execute("SELECT * FROM tasks WHERE task_id = ?", (task_id,)).fetchone()
    if row is None:
        return None
    return _row_to_task(row)


def list_tasks(
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
    with _connect(paths.db_path) as conn:
        rows = conn.execute(query, params).fetchall()
    return [_row_to_task(row) for row in rows]


def _row_to_task(row: sqlite3.Row) -> TaskRecord:
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
    )
