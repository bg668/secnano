from __future__ import annotations

from src.v2.schemas.reply import Reply, Rejection


class SafetyPolicy:
    def check(self, reply: Reply) -> Rejection | None:
        blocked = ("__RAW_MODEL_DUMP__",)
        if any(token in reply.content for token in blocked):
            return Rejection(task_id=reply.task_id, reason="reply failed safety policy")
        return None
