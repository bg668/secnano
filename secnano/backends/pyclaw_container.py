"""Validated-stage container backend."""

from __future__ import annotations

from datetime import UTC, datetime

from secnano.context import ProjectContext
from secnano.models import DelegateRequest, DelegateResult
from secnano.runtime_checks import collect_runtime_checks, summarize_runtime_checks


class PyclawContainerBackend:
    name = "pyclaw_container"

    def __init__(self, ctx: ProjectContext):
        self._ctx = ctx

    def execute(self, request: DelegateRequest) -> DelegateResult:
        start = datetime.now(UTC)
        checks = collect_runtime_checks(self._ctx)
        summary = summarize_runtime_checks(checks)
        if summary["required_fail"] > 0:
            status = "failed"
            output = "pyclaw_container 运行前置校验失败，请先执行 `secnano runtime validate`。"
        else:
            status = "validated"
            output = (
                "pyclaw_container 已通过运行时校验，当前为 validated 阶段。"
                "真实容器执行链路将在后续阶段落地。"
            )
        end = datetime.now(UTC)
        duration_ms = max(1, int((end - start).total_seconds() * 1000))
        return DelegateResult(
            status=status,
            output=output,
            started_at=start.isoformat(),
            finished_at=end.isoformat(),
            duration_ms=duration_ms,
            debug={
                "backend": self.name,
                "runtime_summary": summary,
                "runtime_checks": [item.to_dict() for item in checks],
                "task_chars": len(request.task),
            },
        )

