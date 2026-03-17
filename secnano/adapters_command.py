"""CLI command handlers for adapters."""

from __future__ import annotations

import json

from secnano.adapters import adapter_snapshots
from secnano.context import ProjectContext
from secnano.logging_utils import setup_logging


def run_adapters_list(
    ctx: ProjectContext, *, as_json: bool = False, debug: bool = False
) -> int:
    setup_logging(debug)
    snapshots = adapter_snapshots(ctx)

    if as_json:
        print(json.dumps([item.to_dict() for item in snapshots], ensure_ascii=False, indent=2))
        return 0

    for item in snapshots:
        status = "OK" if item.available else "WARN"
        print(f"[{status}] {item.adapter_id:<20} {item.display_name}")
        print(f"       source: {item.source}")
        print(f"       detail: {item.detail}")
        for cap in item.capabilities:
            tools = ", ".join(cap.tools)
            print(f"       - {cap.capability_id}: {cap.name} [{tools}]")
    return 0

