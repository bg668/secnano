"""
NanoClaw Python — Container Runtime
Mirrors src/container-runtime.ts: runtime detection, orphan cleanup.
"""
from __future__ import annotations

import subprocess

from .config import CONTAINER_NAME_PREFIX, CONTAINER_RUNTIME_BIN
from .logger import logger


def ensure_container_runtime_running() -> None:
    try:
        subprocess.run(
            [CONTAINER_RUNTIME_BIN, "info"],
            capture_output=True,
            timeout=10,
            check=True,
        )
        logger.debug("Container runtime reachable")
    except Exception as exc:
        raise RuntimeError(
            f"Container runtime '{CONTAINER_RUNTIME_BIN}' is unavailable: {exc}"
        ) from exc


def cleanup_orphans() -> None:
    try:
        result = subprocess.run(
            [
                CONTAINER_RUNTIME_BIN,
                "ps",
                "--filter",
                f"name={CONTAINER_NAME_PREFIX}-",
                "--format",
                "{{.Names}}",
            ],
            capture_output=True,
            text=True,
            timeout=10,
        )
        orphans = [n for n in result.stdout.strip().splitlines() if n]
        for name in orphans:
            try:
                subprocess.run(
                    [CONTAINER_RUNTIME_BIN, "stop", name],
                    capture_output=True,
                    timeout=15,
                )
            except Exception:
                pass
        if orphans:
            logger.info(f"Cleaned up orphaned containers count={len(orphans)} names={orphans}")
    except Exception as exc:
        logger.warning(f"Could not clean up orphaned containers: {exc}")
