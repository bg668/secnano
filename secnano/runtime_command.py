"""CLI command handlers for runtime diagnostics."""

from __future__ import annotations

import json

from secnano.context import ProjectContext
from secnano.logging_utils import setup_logging
from secnano.runtime_checks import collect_runtime_checks, summarize_runtime_checks


def run_runtime_inspect(ctx: ProjectContext, *, as_json: bool = False, debug: bool = False) -> int:
    setup_logging(debug)
    checks = collect_runtime_checks(ctx)
    summary = summarize_runtime_checks(checks)
    payload = {
        "checks": [item.to_dict() for item in checks],
        "summary": summary,
    }
    if as_json:
        print(json.dumps(payload, ensure_ascii=False, indent=2))
        return 0

    for item in checks:
        mark = "OK" if item.ok else "MISS"
        req = "required" if item.required else "optional"
        print(f"[{mark:<4}] {item.name:<18} ({req}) {item.detail}")
    print(
        f"summary: ok={summary['ok']} fail={summary['fail']} required_fail={summary['required_fail']}"
    )
    return 0


def run_runtime_validate(
    ctx: ProjectContext, *, as_json: bool = False, debug: bool = False
) -> int:
    setup_logging(debug)
    checks = collect_runtime_checks(ctx)
    summary = summarize_runtime_checks(checks)
    exit_code = 0 if summary["required_fail"] == 0 else 1
    payload = {
        "checks": [item.to_dict() for item in checks],
        "summary": summary,
        "status": "validated" if exit_code == 0 else "failed",
        "exit_code": exit_code,
    }
    if as_json:
        print(json.dumps(payload, ensure_ascii=False, indent=2))
        return exit_code

    for item in checks:
        status = "OK" if item.ok else ("FAIL" if item.required else "WARN")
        print(f"[{status:<4}] {item.name:<18} {item.detail}")
    print(
        f"status={payload['status']} required_fail={summary['required_fail']} exit={exit_code}"
    )
    return exit_code

