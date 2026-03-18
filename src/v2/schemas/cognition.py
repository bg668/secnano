from dataclasses import dataclass

from .inbound import InboundEvent
from .roles import RoleSpec
from .task import ExecutionRequest


@dataclass(frozen=True)
class CognitionRequest:
    inbound: InboundEvent
    role_spec: RoleSpec
    context: tuple[str, ...]


@dataclass(frozen=True)
class CognitionResult:
    thought: str
    execution_request: ExecutionRequest
