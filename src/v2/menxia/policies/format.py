from __future__ import annotations

from src.v2.schemas.reply import Reply, Rejection


class FormatPolicy:
    def __init__(self, max_len: int = 4000):
        self._max_len = max_len

    def check(self, reply: Reply) -> Rejection | None:
        if not reply.content.strip():
            return Rejection(task_id=reply.task_id, reason="reply is empty")
        if len(reply.content) > self._max_len:
            return Rejection(task_id=reply.task_id, reason="reply is too long")
        try:
            reply.content.encode("utf-8")
        except UnicodeError:
            return Rejection(task_id=reply.task_id, reason="reply is not utf-8")
        return None
