"""Capability adapter contracts."""

from __future__ import annotations

from dataclasses import asdict, dataclass
from typing import Any, Protocol

from secnano.context import ProjectContext


@dataclass(frozen=True)
class CapabilitySpec:
    capability_id: str
    name: str
    description: str
    tools: list[str]

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True)
class AdapterSnapshot:
    adapter_id: str
    display_name: str
    source: str
    description: str
    available: bool
    detail: str
    capabilities: list[CapabilitySpec]

    def to_dict(self) -> dict[str, Any]:
        payload = asdict(self)
        payload["capabilities"] = [item.to_dict() for item in self.capabilities]
        return payload


class CapabilityAdapter(Protocol):
    adapter_id: str
    display_name: str
    source: str
    description: str

    def availability(self, ctx: ProjectContext) -> tuple[bool, str]:
        """Return adapter availability and reason/detail."""

    def capabilities(self) -> list[CapabilitySpec]:
        """Return capabilities exported by this adapter."""

