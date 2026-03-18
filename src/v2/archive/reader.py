from __future__ import annotations

import json
from pathlib import Path


class ArchiveReader:
    def __init__(self, runtime_dir: Path | None = None):
        base = runtime_dir or Path("runtime")
        self._tasks_dir = base / "tasks"

    def read_raw(self, task_id: str) -> dict:
        path = self._tasks_dir / f"{task_id}.json"
        return json.loads(path.read_text(encoding="utf-8"))
