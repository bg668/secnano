from dataclasses import dataclass


@dataclass(frozen=True)
class InboundEvent:
    role: str
    task: str
    task_id: str
    created_at: str
