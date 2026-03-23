from __future__ import annotations

"""IPC watcher: processes incoming task files from the IPC directory.

Provides both a one-shot ``watch_once`` function and a long-running
``IPCWatcher`` class that polls in a background thread.
"""

import asyncio
import json
import threading
import time
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from .ipc_auth import is_namespace_allowed
from .paths import ProjectPaths
from .runtime_db import create_task_with_id, utc_now_iso


def _archive_error(
    paths: ProjectPaths,
    *,
    source_path: Path,
    namespace: str,
    error_code: str,
    error_message: str,
) -> Path:
    paths.ipc_errors_dir.mkdir(parents=True, exist_ok=True)
    timestamp = datetime.now(UTC).strftime("%Y%m%dT%H%M%S")
    error_name = f"{timestamp}_{source_path.stem}.json"
    error_path = paths.ipc_errors_dir / error_name
    payload = {
        "version": "v1",
        "source_path": str(source_path),
        "namespace": namespace,
        "error_code": error_code,
        "error_message": error_message,
        "created_at": utc_now_iso(),
    }
    error_path.write_text(json.dumps(payload, ensure_ascii=False), encoding="utf-8")
    return error_path


def _process_task_file(paths: ProjectPaths, task_file: Path) -> dict[str, Any]:
    try:
        payload = json.loads(task_file.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        _archive_error(
            paths,
            source_path=task_file,
            namespace="unknown",
            error_code="IPC_BAD_JSON",
            error_message=str(exc),
        )
        task_file.unlink(missing_ok=True)
        return {"processed": False, "error": "bad_json", "file": str(task_file)}

    namespace = str(payload.get("namespace", "main"))
    if not is_namespace_allowed(namespace):
        _archive_error(
            paths,
            source_path=task_file,
            namespace=namespace,
            error_code="IPC_AUTH_DENIED",
            error_message=f"namespace {namespace} is not allowed",
        )
        task_file.unlink(missing_ok=True)
        return {"processed": False, "error": "auth_denied", "file": str(task_file)}

    try:
        role = str(payload["role"])
        task_id = str(payload["task_id"])
        task_text = str(payload["payload"]["task"])
        max_retries = int(payload.get("options", {}).get("max_retries", 0))
    except (KeyError, TypeError, ValueError) as exc:
        _archive_error(
            paths,
            source_path=task_file,
            namespace=namespace,
            error_code="IPC_INVALID_TASK_PAYLOAD",
            error_message=str(exc),
        )
        task_file.unlink(missing_ok=True)
        return {"processed": False, "error": "invalid_payload", "file": str(task_file)}

    asyncio.run(
        create_task_with_id(
            paths,
            task_id=task_id,
            role=role,
            task=task_text,
            namespace=namespace,
            max_retries=max_retries,
        )
    )
    task_file.unlink(missing_ok=True)
    return {"processed": True, "task_id": task_id, "file": str(task_file)}


def watch_once(paths: ProjectPaths, *, namespace: str) -> list[dict[str, Any]]:
    """Process all pending IPC task files in the given namespace directory once."""
    paths.ensure_ipc_dirs(namespace)
    tasks_dir = paths.ipc_dir / namespace / "tasks"
    results: list[dict[str, Any]] = []
    for task_file in sorted(tasks_dir.glob("*.json")):
        results.append(_process_task_file(paths, task_file))
    return results


class IPCWatcher:
    """Long-running IPC watcher that polls for new task files in a background thread."""

    def __init__(
        self,
        paths: ProjectPaths,
        namespace: str = "main",
        poll_interval: float = 1.0,
    ) -> None:
        self.paths = paths
        self.namespace = namespace
        self.poll_interval = poll_interval
        self._stop_event = threading.Event()
        self._thread: threading.Thread | None = None

    def start(self) -> None:
        """Start the background polling thread."""
        self._stop_event.clear()
        self._thread = threading.Thread(
            target=self._loop,
            name="secnano-ipc-watcher",
            daemon=True,
        )
        self._thread.start()

    def stop(self) -> None:
        """Signal the polling thread to stop and wait for it to exit."""
        self._stop_event.set()
        if self._thread is not None:
            self._thread.join(timeout=5)

    def _loop(self) -> None:
        while not self._stop_event.is_set():
            try:
                watch_once(self.paths, namespace=self.namespace)
            except Exception:
                pass
            self._stop_event.wait(timeout=self.poll_interval)
