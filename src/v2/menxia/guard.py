from __future__ import annotations

from src.v2.menxia.policies.format import FormatPolicy
from src.v2.menxia.policies.safety import SafetyPolicy
from src.v2.schemas.reply import ApprovedReply, Rejection, Reply


class OutputGuard:
    def __init__(self, policies=None):
        self._policies = policies or [FormatPolicy(), SafetyPolicy()]

    def inspect(self, reply: Reply) -> ApprovedReply | Rejection:
        for policy in self._policies:
            rejection = policy.check(reply)
            if rejection is not None:
                return rejection
        return ApprovedReply(task_id=reply.task_id, content=reply.content)
