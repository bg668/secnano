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

