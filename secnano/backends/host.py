"""Host backend for minimal delegation."""

from __future__ import annotations

from datetime import UTC, datetime

from secnano.models import DelegateRequest, DelegateResult


class HostBackend:
    name = "host"

    def execute(self, request: DelegateRequest) -> DelegateResult:
        start = datetime.now(UTC)
        # Milestone 1 minimal execution: build deterministic result for debugging.
        output = (
            f"[host/{request.role}] 任务已执行\n"
            f"task_id={request.task_id}\n"
            f"task={request.task}\n"
            "result=已完成最小委派链路验证"
        )
        end = datetime.now(UTC)
        duration_ms = max(1, int((end - start).total_seconds() * 1000))
        return DelegateResult(
            status="succeeded",
            output=output,
            started_at=start.isoformat(),
            finished_at=end.isoformat(),
            duration_ms=duration_ms,
            debug={
                "backend": self.name,
                "task_chars": len(request.task),
                "role": request.role,
            },
        )

