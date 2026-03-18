"""子进程后端——真正执行 agent loop 的 backend。

将 secnano 现有的 SubagentBackend Protocol（base.py）与
子进程执行层（process/pool.py）桥接起来。
"""

from __future__ import annotations

import asyncio
from datetime import UTC, datetime
from typing import Any

from secnano.context import ProjectContext
from secnano.models import DelegateRequest, DelegateResult
from secnano.process.pool import ProcessPool
from secnano.process.protocol import WorkerInput, WorkerMessage


class SubprocessBackend:
    name = "subprocess"

    def __init__(self, ctx: ProjectContext, max_concurrent: int = 4):
        self._ctx = ctx
        self._max_concurrent = max_concurrent

    def execute(self, request: DelegateRequest) -> DelegateResult:
        """同步包装异步执行（delegate_command 当前是同步调用链）。"""
        start = datetime.now(UTC)
        tool_calls: list[dict[str, Any]] = []

        # 确保 workspace 目录存在
        workspace_dir = self._ctx.workspace_dir
        workspace_dir.mkdir(parents=True, exist_ok=True)

        worker_input = WorkerInput(
            task_id=request.task_id,
            role=request.role,
            task=request.task,
            workspace=str(workspace_dir),
            role_dir=str(self._ctx.roles_dir / request.role),
        )

        async def _run() -> WorkerMessage:
            pool = ProcessPool(max_concurrent=self._max_concurrent)

            async def on_message(msg: WorkerMessage) -> None:
                if msg.type == "tool_call":
                    tool_calls.append(msg.metadata)

            return await pool.run(worker_input, on_message=on_message)

        result_msg = asyncio.run(_run())

        end = datetime.now(UTC)
        duration_ms = max(1, int((end - start).total_seconds() * 1000))

        return DelegateResult(
            status="succeeded" if result_msg.type == "result" else "failed",
            output=result_msg.content,
            started_at=start.isoformat(),
            finished_at=end.isoformat(),
            duration_ms=duration_ms,
            debug={
                "backend": self.name,
                "role": request.role,
                "task_chars": len(request.task),
                "tool_calls": tool_calls,
                "tool_call_count": len(tool_calls),
            },
        )
