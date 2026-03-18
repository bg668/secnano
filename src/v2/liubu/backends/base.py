from __future__ import annotations

from typing import Protocol

from src.v2.schemas.task import ExecutionRequest, ExecutionResult


class ExecutionBackend(Protocol):
    def execute(self, request: ExecutionRequest) -> ExecutionResult: ...
