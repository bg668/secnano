from __future__ import annotations

import json
from dataclasses import asdict
from pathlib import Path

from src.v2.schemas.archive import TaskArchiveRecord


class ArchiveWriter:
    def __init__(self, runtime_dir: Path | None = None):
        base = runtime_dir or Path("runtime")
        self._tasks_dir = base / "tasks"
        self._tasks_dir.mkdir(parents=True, exist_ok=True)

    def write(self, record: TaskArchiveRecord) -> Path:
        path = self._tasks_dir / f"{record.task_id}.json"
        payload = asdict(record)
        path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
        return path
