from __future__ import annotations

from src.v2.liubu.tools.registry import ToolRegistry
from src.v2.schemas.task import ExecutionRequest, ExecutionResult


class HostExecutionBackend:
    def __init__(self, registry: ToolRegistry | None = None):
        self._registry = registry or ToolRegistry()

    def execute(self, request: ExecutionRequest) -> ExecutionResult:
        result = self._registry.dispatch(request.tool_name, request.arguments)
        return ExecutionResult(
            task_id=request.task_id,
            tool_name=request.tool_name,
            success=result.success,
            output=result.output,
            exit_code=result.exit_code,
        )
