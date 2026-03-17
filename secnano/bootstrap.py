"""Bootstrap local development environment for secnano."""

from __future__ import annotations

import json
import subprocess
import sys
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any

from secnano.context import ProjectContext


@dataclass(frozen=True)
class BootstrapStep:
    name: str
    command: list[str]
    enabled: bool
    reason: str

    def to_dict(self) -> dict[str, Any]:
        payload = asdict(self)
        payload["command"] = " ".join(self.command)
        return payload


def _build_steps(ctx: ProjectContext) -> list[BootstrapStep]:
    packages_nanobot = ctx.packages_dir / "nanobot"
    venv_exists = ctx.venv_python.exists()
    bootstrap_python = str(ctx.venv_python if venv_exists else Path(sys.executable))

    steps = [
        BootstrapStep(
            name="create_venv",
            command=[sys.executable, "-m", "venv", str(ctx.venv_dir)],
            enabled=not ctx.venv_dir.exists(),
            reason="创建本地 .venv 虚拟环境",
        ),
        BootstrapStep(
            name="install_nanobot_editable",
            command=[bootstrap_python, "-m", "pip", "install", "-e", str(packages_nanobot)],
            enabled=(packages_nanobot / "pyproject.toml").exists(),
            reason="安装 packages/nanobot editable 依赖",
        ),
        BootstrapStep(
            name="install_secnano_editable",
            command=[bootstrap_python, "-m", "pip", "install", "-e", str(ctx.project_root)],
            enabled=(ctx.project_root / "pyproject.toml").exists(),
            reason="安装 secnano editable 包",
        ),
    ]
    return steps


def _print_step(step: BootstrapStep) -> None:
    command = " ".join(step.command)
    if step.enabled:
        print(f"[PLAN] {step.name:<28} {step.reason}")
        print(f"       {command}")
    else:
        print(f"[SKIP] {step.name:<28} {step.reason}")


def run_bootstrap(ctx: ProjectContext, *, dry_run: bool, as_json: bool = False) -> int:
    steps = _build_steps(ctx)
    results: list[dict[str, Any]] = []

    for step in steps:
        if dry_run:
            _print_step(step)
            results.append(
                {
                    **step.to_dict(),
                    "status": "planned" if step.enabled else "skipped",
                    "returncode": None,
                }
            )
            continue

        if not step.enabled:
            print(f"[SKIP] {step.name}")
            results.append(
                {
                    **step.to_dict(),
                    "status": "skipped",
                    "returncode": None,
                }
            )
            continue

        print(f"[RUN ] {step.name}")
        proc = subprocess.run(step.command, cwd=ctx.project_root, check=False)
        status = "ok" if proc.returncode == 0 else "fail"
        results.append(
            {
                **step.to_dict(),
                "status": status,
                "returncode": proc.returncode,
            }
        )
        if proc.returncode != 0:
            if as_json:
                print(
                    json.dumps(
                        {
                            "dry_run": dry_run,
                            "results": results,
                            "exit_code": proc.returncode,
                        },
                        ensure_ascii=False,
                        indent=2,
                    )
                )
            return proc.returncode

    exit_code = 0
    if as_json:
        payload = {"dry_run": dry_run, "results": results, "exit_code": exit_code}
        print(json.dumps(payload, ensure_ascii=False, indent=2))
    elif dry_run:
        print("dry-run 完成：未执行任何系统修改。")
    else:
        print("bootstrap 完成。")
    return exit_code
