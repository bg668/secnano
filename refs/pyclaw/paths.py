"""
Standalone project paths for the extracted NanoClaw Python learning repo.
"""
from __future__ import annotations

import os
from pathlib import Path


def _resolve_path(env_name: str, default: Path) -> Path:
    override = os.environ.get(env_name)
    candidate = Path(override).expanduser() if override else default
    return candidate.resolve()


PACKAGE_DIR = Path(__file__).resolve().parent
PROJECT_ROOT = _resolve_path("NAOCLAW_PY_ROOT", PACKAGE_DIR.parent)
CONFIG_DIR = _resolve_path("NAOCLAW_PY_CONFIG_DIR", PROJECT_ROOT / "config")
GROUPS_DIR = _resolve_path("NAOCLAW_PY_GROUPS_DIR", PROJECT_ROOT / "groups")
DATA_DIR = _resolve_path("NAOCLAW_PY_DATA_DIR", PROJECT_ROOT / "data")
STORE_DIR = _resolve_path("NAOCLAW_PY_STORE_DIR", PROJECT_ROOT / "store")
CONTAINER_DIR = _resolve_path("NAOCLAW_PY_CONTAINER_DIR", PROJECT_ROOT / "container")