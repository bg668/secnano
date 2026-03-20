from __future__ import annotations

import json
import uuid
from pathlib import Path
from typing import Any

from .paths import ProjectPaths
from .runtime_db import create_task_id, utc_now_iso


def build_task_request(
    *,
    role: str,
    task: str,
    namespace: str = "main",
    timeout_sec: int = 120,
    max_retries: int = 0,
) -> dict[str, Any]:
    task_id = create_task_id()
    return {
        "version": "v1",
        "request_id": f"req_{uuid.uuid4().hex[:12]}",
        "task_id": task_id,
        "namespace": namespace,
        "role": role,
        "created_at": utc_now_iso(),
        "payload": {"task": task, "context": {"source": "cli"}},
        "options": {
            "timeout_sec": timeout_sec,
            "max_retries": max_retries,
            "idempotency_key": task_id,
        },
    }


def write_task_file(paths: ProjectPaths, payload: dict[str, Any]) -> Path:
    namespace = str(payload.get("namespace", "main"))
    task_id = str(payload["task_id"])
    paths.ensure_ipc_dirs(namespace)
    tasks_dir = paths.ipc_dir / namespace / "tasks"
    final_path = tasks_dir / f"{task_id}.json"
    tmp_path = Path(str(final_path) + ".tmp")
    tmp_path.write_text(json.dumps(payload, ensure_ascii=False), encoding="utf-8")
    tmp_path.replace(final_path)
    return final_path
