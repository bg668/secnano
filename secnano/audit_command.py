"""CLI command handlers for audit."""

from __future__ import annotations

import json
from dataclasses import asdict

from secnano.archive import TaskArchiveStore
from secnano.context import ProjectContext
from secnano.logging_utils import setup_logging


def run_audit_list(
    ctx: ProjectContext, *, limit: int = 20, as_json: bool = False, debug: bool = False
) -> int:
    setup_logging(debug)
    records = TaskArchiveStore(ctx).list_records(limit=limit)
    if as_json:
        print(json.dumps([asdict(item) for item in records], ensure_ascii=False, indent=2))
        return 0

    if not records:
        print("未发现归档任务。")
        return 0

    for item in records:
        print(
            f"{item.task_id} | {item.status:<9} | {item.backend:<6} | {item.role:<18} | {item.finished_at}"
        )
    return 0


def run_audit_show(
    ctx: ProjectContext, *, task_id: str, as_json: bool = False, debug: bool = False
) -> int:
    setup_logging(debug)
    record = TaskArchiveStore(ctx).get_record(task_id)
    if record is None:
        print(f"未找到任务归档：{task_id}")
        return 2

    payload = asdict(record)
    if as_json:
        print(json.dumps(payload, ensure_ascii=False, indent=2))
        return 0

    print(f"task_id: {record.task_id}")
    print(f"backend: {record.backend}")
    print(f"role: {record.role}")
    print(f"status: {record.status}")
    print(f"created_at: {record.created_at}")
    print(f"finished_at: {record.finished_at}")
    print(f"duration_ms: {record.duration_ms}")
    print("--- TASK ---")
    print(record.task)
    print("--- OUTPUT ---")
    print(record.output)
    return 0
