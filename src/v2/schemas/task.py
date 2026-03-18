from dataclasses import dataclass, field
from typing import Mapping


@dataclass(frozen=True)
class Task:
    task_id: str
    role: str
    content: str


@dataclass(frozen=True)
class ExecutionRequest:
    task_id: str
    tool_name: str
    arguments: tuple[str, ...] = ()
    metadata: Mapping[str, str] = field(default_factory=dict)


@dataclass(frozen=True)
class ExecutionResult:
    task_id: str
    tool_name: str
    success: bool
    output: str
    exit_code: int = 0
