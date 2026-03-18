from dataclasses import dataclass


@dataclass(frozen=True)
class Reply:
    task_id: str
    content: str


@dataclass(frozen=True)
class ApprovedReply:
    task_id: str
    content: str


@dataclass(frozen=True)
class Rejection:
    task_id: str
    reason: str
