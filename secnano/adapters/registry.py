"""Adapter registry and snapshots."""

from __future__ import annotations

from secnano.adapters.base import AdapterSnapshot, CapabilityAdapter
from secnano.adapters.builtin import (
    HostExecutionAdapter,
    NanobotRuntimeAdapter,
    PyclawContainerAdapter,
)
from secnano.context import ProjectContext


def load_adapters() -> list[CapabilityAdapter]:
    return [
        HostExecutionAdapter(),
        PyclawContainerAdapter(),
        NanobotRuntimeAdapter(),
    ]


def adapter_snapshots(ctx: ProjectContext) -> list[AdapterSnapshot]:
    snapshots: list[AdapterSnapshot] = []
    for adapter in load_adapters():
        available, detail = adapter.availability(ctx)
        snapshots.append(
            AdapterSnapshot(
                adapter_id=adapter.adapter_id,
                display_name=adapter.display_name,
                source=adapter.source,
                description=adapter.description,
                available=available,
                detail=detail,
                capabilities=adapter.capabilities(),
            )
        )
    return snapshots

