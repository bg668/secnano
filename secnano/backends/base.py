"""Backend contracts."""

from __future__ import annotations

from typing import Protocol

from secnano.models import DelegateRequest, DelegateResult


class SubagentBackend(Protocol):
    name: str

    def execute(self, request: DelegateRequest) -> DelegateResult:
        """Execute a delegated task request."""

