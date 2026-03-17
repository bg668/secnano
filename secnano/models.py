"""Core models used by secnano runtime."""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from datetime import UTC, datetime
from typing import Any


def utc_now_iso() -> str:
    return datetime.now(UTC).isoformat()


@dataclass(frozen=True)
class RoleInfo:
    name: str
    path: str
    has_role_md: bool

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True)
class DelegateRequest:
    task_id: str
    backend: str
    role: str
    task: str
    created_at: str = field(default_factory=utc_now_iso)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True)
class DelegateResult:
    status: str
    output: str
    started_at: str
    finished_at: str
    duration_ms: int
    debug: dict[str, Any]

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True)
class TaskArchiveRecord:
    task_id: str
    backend: str
    role: str
    task: str
    status: str
    output: str
    created_at: str
    finished_at: str
    duration_ms: int
    debug: dict[str, Any]

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

