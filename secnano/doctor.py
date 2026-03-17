"""Health checks for local secnano runtime."""

from __future__ import annotations

import json
import sys
from dataclasses import asdict, dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from secnano.context import ProjectContext
from secnano.runtime_bridge import inspect_nanobot_bridge


@dataclass(frozen=True)
class CheckResult:
    name: str
    status: str
    detail: str

    def to_dict(self) -> dict[str, str]:
        return asdict(self)


def _check_python_version() -> CheckResult:
    required = (3, 14)
    current = sys.version_info[:3]
    if current >= required:
        return CheckResult(
            name="python_version",
            status="ok",
            detail=f"当前 Python {current[0]}.{current[1]}.{current[2]}，满足 >=3.14",
        )
    return CheckResult(
        name="python_version",
        status="fail",
        detail=f"当前 Python {current[0]}.{current[1]}.{current[2]}，不满足 >=3.14",
    )


def _check_path_exists(name: str, path: Path, optional: bool = False) -> CheckResult:
    if path.exists():
        return CheckResult(name=name, status="ok", detail=f"存在：{path}")
    if optional:
        return CheckResult(name=name, status="warn", detail=f"未找到（可选）：{path}")
    return CheckResult(name=name, status="fail", detail=f"未找到：{path}")


def run_doctor(ctx: ProjectContext, *, as_json: bool = False) -> int:
    checks = [
        _check_python_version(),
        _check_path_exists("packages_nanobot", ctx.packages_dir / "nanobot"),
        _check_path_exists("refs_pyclaw", ctx.refs_dir / "pyclaw"),
        _check_path_exists("refs_nanoclaw", ctx.refs_dir / "nanoclaw"),
        _check_path_exists("venv_dir", ctx.venv_dir, optional=True),
        _check_path_exists("venv_python", ctx.venv_python, optional=True),
    ]

    bridge = inspect_nanobot_bridge(ctx.packages_dir / "nanobot")
    checks.append(
        CheckResult(
            name="nanobot_runtime_bridge",
            status="ok" if bridge.available else "warn",
            detail=(
                f"可导入 nanobot：{bridge.import_location}"
                if bridge.available
                else "未导入 nanobot，请执行 bootstrap 安装 packages/nanobot editable 依赖"
            ),
        )
    )

    summary = {
        "ok": sum(1 for item in checks if item.status == "ok"),
        "warn": sum(1 for item in checks if item.status == "warn"),
        "fail": sum(1 for item in checks if item.status == "fail"),
    }
    exit_code = 1 if summary["fail"] else 0

    if as_json:
        payload: dict[str, Any] = {
            "timestamp": datetime.now(UTC).isoformat(),
            "checks": [item.to_dict() for item in checks],
            "runtime_bridge": bridge.to_dict(),
            "summary": summary,
            "exit_code": exit_code,
        }
        print(json.dumps(payload, ensure_ascii=False, indent=2))
        return exit_code

    for item in checks:
        print(f"[{item.status.upper():4}] {item.name:<24} {item.detail}")
    print(
        f"summary: ok={summary['ok']} warn={summary['warn']} fail={summary['fail']} exit={exit_code}"
    )
    return exit_code
