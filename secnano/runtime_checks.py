"""Runtime checks for container-prep stage."""

from __future__ import annotations

import shutil
import subprocess
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any

from secnano.context import ProjectContext


@dataclass(frozen=True)
class RuntimeCheck:
    name: str
    ok: bool
    required: bool
    detail: str

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


def _read_version(executable: str, version_args: list[str]) -> str:
    try:
        proc = subprocess.run(
            [executable, *version_args],
            check=False,
            capture_output=True,
            text=True,
        )
    except OSError:
        return "unavailable"
    output = (proc.stdout or proc.stderr).strip()
    if not output:
        return "unavailable"
    return output.splitlines()[0]


def _check_binary(name: str, *, required: bool, version_args: list[str]) -> RuntimeCheck:
    path = shutil.which(name)
    if path is None:
        return RuntimeCheck(
            name=name,
            ok=False,
            required=required,
            detail="not found in PATH",
        )
    version = _read_version(path, version_args)
    return RuntimeCheck(
        name=name,
        ok=True,
        required=required,
        detail=f"{path} ({version})",
    )


def _check_path(name: str, path: Path, *, required: bool) -> RuntimeCheck:
    return RuntimeCheck(
        name=name,
        ok=path.exists(),
        required=required,
        detail=str(path),
    )


def collect_runtime_checks(ctx: ProjectContext) -> list[RuntimeCheck]:
    return [
        _check_binary("docker", required=True, version_args=["--version"]),
        _check_binary("node", required=True, version_args=["--version"]),
        _check_binary("npm", required=True, version_args=["--version"]),
        _check_path("refs_pyclaw", ctx.refs_dir / "pyclaw", required=True),
        _check_path("refs_nanoclaw", ctx.refs_dir / "nanoclaw", required=True),
        _check_path("packages_nanobot", ctx.packages_dir / "nanobot", required=False),
    ]


def summarize_runtime_checks(checks: list[RuntimeCheck]) -> dict[str, int]:
    required_failures = sum(1 for item in checks if item.required and not item.ok)
    return {
        "ok": sum(1 for item in checks if item.ok),
        "fail": sum(1 for item in checks if not item.ok),
        "required_fail": required_failures,
    }

