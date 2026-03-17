"""CLI command handler for tools catalog."""

from __future__ import annotations

import json
from typing import Any

from secnano.adapters import adapter_snapshots
from secnano.context import ProjectContext
from secnano.logging_utils import setup_logging


def _build_tools_payload(ctx: ProjectContext) -> list[dict[str, Any]]:
    index: dict[str, dict[str, Any]] = {}
    for snapshot in adapter_snapshots(ctx):
        for capability in snapshot.capabilities:
            for tool in capability.tools:
                entry = index.setdefault(
                    tool,
                    {
                        "tool": tool,
                        "adapters": [],
                        "capabilities": [],
                        "available": False,
                    },
                )
                entry["adapters"].append(snapshot.adapter_id)
                entry["capabilities"].append(capability.capability_id)
                entry["available"] = entry["available"] or snapshot.available

    payload = list(index.values())
    for item in payload:
        item["adapters"] = sorted(set(item["adapters"]))
        item["capabilities"] = sorted(set(item["capabilities"]))
    payload.sort(key=lambda row: row["tool"])
    return payload


def run_tools(ctx: ProjectContext, *, as_json: bool = False, debug: bool = False) -> int:
    setup_logging(debug)
    payload = _build_tools_payload(ctx)

    if as_json:
        print(json.dumps(payload, ensure_ascii=False, indent=2))
        return 0

    for item in payload:
        status = "OK" if item["available"] else "WARN"
        adapters = ",".join(item["adapters"])
        capabilities = ",".join(item["capabilities"])
        print(f"[{status}] {item['tool']:<26} adapters={adapters} capabilities={capabilities}")
    return 0

