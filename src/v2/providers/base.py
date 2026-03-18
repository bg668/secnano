from __future__ import annotations

from typing import Protocol


class AIProvider(Protocol):
    def generate(self, prompt: str) -> str: ...


class RuleBasedProvider:
    def generate(self, prompt: str) -> str:
        task = prompt.rsplit("TASK:\n", 1)[-1].split("\n\n", 1)[0].strip()
        lower = task.lower()
        if "run echo" in lower:
            suffix = task.split("run echo", 1)[1].strip() or "ok"
            return f"TOOL:echo ARGS:{suffix}"
        if "hello" in lower:
            return "TOOL:echo ARGS:hello"
        return "TOOL:echo ARGS:done"
