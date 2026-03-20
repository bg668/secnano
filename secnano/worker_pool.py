from __future__ import annotations

"""WorkerPool: manages subprocess workers that execute pending tasks.

Usage:
    pool = WorkerPool(paths, max_workers=4, task_timeout=300)
    pool.start()     # starts background scheduler thread
    pool.stop()      # graceful shutdown
    pool.status()    # returns {active, waiting, max_workers, running_task_ids}
    pool.enqueue(task_id, payload)  # add a task to waiting queue
"""

import base64
import json
import logging
import subprocess
import sys
import threading
import time
from pathlib import Path

from .paths import ProjectPaths
from .runtime_db import (
    append_run_log,
    claim_task,
    list_pending_tasks,
    mark_failed,
)

logger = logging.getLogger(__name__)

_SCHEDULER_INTERVAL = 5.0  # seconds between scheduler ticks


class WorkerPool:
    def __init__(
        self,
        paths: ProjectPaths,
        max_workers: int = 4,
        task_timeout: int = 300,
    ) -> None:
        self.paths = paths
        self.max_workers = max_workers
        self.task_timeout = task_timeout

        self._lock = threading.Lock()
        self._waiting: list[tuple[str, dict]] = []  # (task_id, payload)
        self._active: dict[str, subprocess.Popen] = {}  # task_id -> proc
        self._start_times: dict[str, float] = {}  # task_id -> monotonic start time
        self._stop_event = threading.Event()
        self._scheduler_thread: threading.Thread | None = None

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def start(self) -> None:
        """Start the background scheduler thread."""
        self._stop_event.clear()
        self._scheduler_thread = threading.Thread(
            target=self._scheduler_loop,
            name="secnano-worker-scheduler",
            daemon=True,
        )
        self._scheduler_thread.start()
        logger.info("WorkerPool started (max_workers=%d, timeout=%ds)", self.max_workers, self.task_timeout)

    def stop(self) -> None:
        """Signal stop and wait for the scheduler thread to exit."""
        self._stop_event.set()
        if self._scheduler_thread is not None:
            self._scheduler_thread.join(timeout=10)
        logger.info("WorkerPool stopped")

    def status(self) -> dict:
        with self._lock:
            running_task_ids = list(self._active.keys())
            waiting = len(self._waiting)
        return {
            "active": len(running_task_ids),
            "waiting": waiting,
            "max_workers": self.max_workers,
            "running_task_ids": running_task_ids,
        }

    def enqueue(self, task_id: str, payload: dict) -> None:
        """Add a task to the waiting queue."""
        with self._lock:
            # Avoid duplicate enqueue
            existing_ids = {t for t, _ in self._waiting} | set(self._active.keys())
            if task_id not in existing_ids:
                self._waiting.append((task_id, payload))
                logger.debug("Enqueued task %s", task_id)

    # ------------------------------------------------------------------
    # Internal scheduler
    # ------------------------------------------------------------------

    def _scheduler_loop(self) -> None:
        while not self._stop_event.is_set():
            try:
                self._reap_finished()
                self._scan_pending_db()
                self._drain_waiting()
            except Exception:
                logger.exception("Scheduler tick error")
            self._stop_event.wait(timeout=_SCHEDULER_INTERVAL)

    def _reap_finished(self) -> None:
        """Poll running processes and handle any that have exited."""
        with self._lock:
            finished = [
                (task_id, proc, self._start_times.get(task_id))
                for task_id, proc in self._active.items()
                if proc.poll() is not None
            ]
        for task_id, proc, start_time in finished:
            self._on_worker_exit(task_id, proc, start_time=start_time)

    def _scan_pending_db(self) -> None:
        """Pull pending tasks from the DB and enqueue them."""
        try:
            tasks = list_pending_tasks(self.paths, limit=self.max_workers * 2)
        except Exception:
            logger.exception("Failed to scan pending tasks from DB")
            return

        with self._lock:
            existing = {t for t, _ in self._waiting} | set(self._active.keys())

        for task in tasks:
            if task.task_id not in existing:
                self.enqueue(task.task_id, task.payload)

    def _drain_waiting(self) -> None:
        """Spawn workers for waiting tasks up to max_workers limit."""
        while True:
            with self._lock:
                active_count = len(self._active)
                if active_count >= self.max_workers or not self._waiting:
                    break
                task_id, payload = self._waiting.pop(0)

            if not self._try_spawn_by_id(task_id, payload):
                logger.debug("Could not claim task %s, skipping", task_id)

    def _try_spawn_by_id(self, task_id: str, payload: dict) -> bool:
        """Attempt to claim and spawn a worker for the given task."""
        worker_id = f"worker-{task_id[:8]}"
        if not claim_task(self.paths, task_id, worker_id):
            return False
        self._spawn_worker(task_id, payload, worker_id)
        return True

    def _try_spawn(self, task) -> bool:  # noqa: ANN001
        return self._try_spawn_by_id(task.task_id, task.payload)

    def _spawn_worker(self, task_id: str, payload: dict, worker_id: str) -> None:
        """Launch subprocess for the subagent."""
        task_data = {
            "task_id": task_id,
            "role": payload.get("role", "general_office"),
            "payload": payload,
            "db_path": str(self.paths.db_path),
            "worker_id": worker_id,
        }
        task_json_b64 = base64.b64encode(
            json.dumps(task_data, ensure_ascii=False).encode("utf-8")
        ).decode("ascii")

        cmd = [sys.executable, "-m", "secnano._subagent", task_json_b64]
        try:
            proc = subprocess.Popen(
                cmd,
                cwd=str(self.paths.root_dir),
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
            )
        except Exception as exc:
            logger.error("Failed to spawn worker for task %s: %s", task_id, exc)
            try:
                mark_failed(self.paths, task_id, error=f"spawn_error: {exc}")
            except Exception:
                pass
            return

        with self._lock:
            self._active[task_id] = proc
            self._start_times[task_id] = time.monotonic()

        # Start a watcher thread so we get timeout handling
        start_time = self._start_times[task_id]
        watcher = threading.Thread(
            target=self._wait_for_worker,
            args=(task_id, proc, start_time),
            name=f"secnano-worker-watcher-{task_id[:8]}",
            daemon=True,
        )
        watcher.start()
        logger.info("Spawned worker for task %s (pid=%d)", task_id, proc.pid)

    def _wait_for_worker(self, task_id: str, proc: subprocess.Popen, start_time: float) -> None:
        """Wait for a worker process to finish (with timeout)."""
        try:
            proc.wait(timeout=self.task_timeout)
        except subprocess.TimeoutExpired:
            logger.warning("Task %s timed out after %ds, killing", task_id, self.task_timeout)
            proc.kill()
            try:
                proc.wait(timeout=5)
            except Exception:
                pass
            try:
                mark_failed(self.paths, task_id, error=f"timeout after {self.task_timeout}s")
            except Exception:
                logger.exception("Failed to mark_failed for timed-out task %s", task_id)
        finally:
            self._on_worker_exit(task_id, proc, start_time)

    def _on_worker_exit(self, task_id: str, proc: subprocess.Popen, start_time: float | None) -> None:
        """Handle worker process exit: log result."""
        returncode = proc.returncode
        duration_ms: int | None = None
        if start_time is not None:
            duration_ms = int((time.monotonic() - start_time) * 1000)

        # Collect stderr for logging
        stderr_output = ""
        if proc.stderr:
            try:
                raw = proc.stderr.read()
                if raw:
                    stderr_output = raw.decode("utf-8", errors="replace")
            except Exception:
                pass

        if returncode == 0:
            status = "done"
            logger.info("Task %s completed successfully (duration=%sms)", task_id, duration_ms)
        else:
            status = "failed"
            logger.warning(
                "Task %s failed (returncode=%d, stderr=%s)",
                task_id,
                returncode,
                stderr_output[:200],
            )

        try:
            append_run_log(
                self.paths,
                task_id=task_id,
                attempt_no=1,
                worker_id=f"worker-{task_id[:8]}",
                status=status,
                duration_ms=duration_ms,
                error_text=stderr_output[:1000] if returncode != 0 else None,
                result=None,
            )
        except Exception:
            logger.exception("Failed to append_run_log for task %s", task_id)

        with self._lock:
            self._active.pop(task_id, None)
            self._start_times.pop(task_id, None)
