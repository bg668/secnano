from dataclasses import dataclass


@dataclass(frozen=True)
class ToolSpec:
    name: str
    description: str
