"""Task archive persistence."""

from __future__ import annotations

import json
from pathlib import Path

from secnano.context import ProjectContext
from secnano.models import TaskArchiveRecord


class TaskArchiveStore:
    def __init__(self, ctx: ProjectContext):
        self._dir: Path = ctx.runtime_tasks_dir
        self._dir.mkdir(parents=True, exist_ok=True)

    def save(self, record: TaskArchiveRecord) -> Path:
        output_path = self._dir / f"{record.task_id}.json"
        output_path.write_text(
            json.dumps(record.to_dict(), ensure_ascii=False, indent=2) + "\n",
            encoding="utf-8",
        )
        return output_path

    def list_records(self, *, limit: int = 20) -> list[TaskArchiveRecord]:
        files = sorted(
            self._dir.glob("*.json"),
            key=lambda path: path.stat().st_mtime,
            reverse=True,
        )[:limit]
        records: list[TaskArchiveRecord] = []
        for file_path in files:
            payload = json.loads(file_path.read_text(encoding="utf-8"))
            records.append(TaskArchiveRecord(**payload))
        return records
