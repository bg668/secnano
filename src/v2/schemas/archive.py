from dataclasses import dataclass
from typing import Optional

from .inbound import InboundEvent
from .cognition import CognitionResult
from .reply import ApprovedReply, Rejection, Reply
from .task import ExecutionResult


@dataclass(frozen=True)
class TaskArchiveRecord:
    task_id: str
    inbound: InboundEvent
    cognition: CognitionResult
    execution: ExecutionResult
    reply: Reply
    guarded: ApprovedReply | Rejection
    error: Optional[str] = None
