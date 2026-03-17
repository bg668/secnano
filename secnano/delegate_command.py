"""CLI command handlers for delegation."""

from __future__ import annotations

import json
import logging
from uuid import uuid4

from secnano.archive import TaskArchiveStore
from secnano.backends import HostBackend, PyclawContainerBackend, SubagentBackend
from secnano.context import ProjectContext
from secnano.logging_utils import setup_logging
from secnano.models import DelegateRequest, TaskArchiveRecord
from secnano.roles import role_exists

logger = logging.getLogger(__name__)


def _backend_registry(ctx: ProjectContext) -> dict[str, SubagentBackend]:
    return {
        "host": HostBackend(),
        "pyclaw_container": PyclawContainerBackend(ctx),
    }


def run_delegate(
    ctx: ProjectContext,
    *,
    backend_name: str,
    role: str,
    task: str,
    as_json: bool = False,
    debug: bool = False,
) -> int:
    setup_logging(debug)
    if not role_exists(ctx, role):
        print(f"角色不存在或缺少 ROLE.md：{role}。请先执行 `secnano roles ensure-defaults`。")
        return 2

    backend_registry = _backend_registry(ctx)
    backend = backend_registry.get(backend_name)
    if backend is None:
        available = ", ".join(sorted(backend_registry))
        print(f"不支持的 backend：{backend_name}。当前支持：{available}")
        return 2

    task_id = uuid4().hex[:12]
    request = DelegateRequest(
        task_id=task_id,
        backend=backend_name,
        role=role,
        task=task,
    )
    logger.debug("delegate request=%s", request.to_dict())
    result = backend.execute(request)
    record = TaskArchiveRecord(
        task_id=request.task_id,
        backend=request.backend,
        role=request.role,
        task=request.task,
        status=result.status,
        output=result.output,
        created_at=request.created_at,
        finished_at=result.finished_at,
        duration_ms=result.duration_ms,
        debug=result.debug,
    )
    archive_path = TaskArchiveStore(ctx).save(record)

    payload = {
        "task_id": request.task_id,
        "backend": request.backend,
        "role": request.role,
        "status": result.status,
        "output": result.output,
        "archive_path": str(archive_path),
        "duration_ms": result.duration_ms,
        "debug": result.debug,
    }
    if as_json:
        print(json.dumps(payload, ensure_ascii=False, indent=2))
    else:
        print(f"delegate 完成: task_id={request.task_id} status={result.status}")
        print(result.output)
        print(f"archive: {archive_path}")
    return 0 if result.status in {"succeeded", "validated"} else 1
