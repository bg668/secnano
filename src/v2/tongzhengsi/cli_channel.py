from __future__ import annotations

from datetime import datetime, timezone
from uuid import uuid4

from src.v2.schemas.inbound import InboundEvent

from .validator import validate_role, validate_task


def build_inbound_event(role: str, task: str) -> InboundEvent:
    return InboundEvent(
        role=validate_role(role),
        task=validate_task(task),
        task_id=uuid4().hex,
        created_at=datetime.now(timezone.utc).isoformat(),
    )
