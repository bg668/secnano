from __future__ import annotations

from dataclasses import dataclass

from .specs import ToolSpec


@dataclass(frozen=True)
class ToolResult:
    success: bool
    output: str
    exit_code: int


class ToolRegistry:
    def __init__(self):
        self._specs = {
            "echo": ToolSpec(name="echo", description="Return joined arguments as output"),
        }

    def list_tools(self) -> tuple[ToolSpec, ...]:
        return tuple(self._specs.values())

    def dispatch(self, tool_name: str, arguments: tuple[str, ...]) -> ToolResult:
        if tool_name == "echo":
            return ToolResult(success=True, output=" ".join(arguments), exit_code=0)
        return ToolResult(success=False, output=f"unknown tool: {tool_name}", exit_code=1)
