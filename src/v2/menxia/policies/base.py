from __future__ import annotations

from typing import Protocol

from src.v2.schemas.reply import Reply, Rejection


class PolicyRule(Protocol):
    def check(self, reply: Reply) -> Rejection | None: ...
