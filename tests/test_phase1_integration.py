from __future__ import annotations

"""Phase 1 integration tests: task lifecycle, scheduling, retry, and logs."""

import asyncio
import json
import shutil
import subprocess
import unittest
from datetime import UTC, datetime, timedelta
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
PYTHON = "python3"


def _make_paths(tmp_dir: Path):
    from secnano.paths import ProjectPaths

    db_dir = tmp_dir / "runtime" / "db"
    db_dir.mkdir(parents=True, exist_ok=True)
    return ProjectPaths(
        root_dir=tmp_dir,
        runtime_dir=tmp_dir / "runtime",
        db_dir=db_dir,
        db_path=db_dir / "secnano.sqlite3",
        ipc_dir=tmp_dir / "runtime" / "ipc",
        ipc_errors_dir=tmp_dir / "runtime" / "ipc" / "errors",
    )


class TestPhase1TaskLifecycle(unittest.TestCase):
    """Tests covering the full task state machine."""

    def setUp(self) -> None:
        self._tmp = Path("/tmp/secnano-phase1-test")
        if self._tmp.exists():
            shutil.rmtree(self._tmp)
        self._tmp.mkdir(parents=True, exist_ok=True)
        self.paths = _make_paths(self._tmp)
        from secnano.runtime_db import init_db
        asyncio.run(init_db(self.paths))

    def tearDown(self) -> None:
        if self._tmp.exists():
            shutil.rmtree(self._tmp)

    def _submit(self, task_text: str = "test task") -> str:
        from secnano.runtime_db import create_task
        task = asyncio.run(create_task(self.paths, role="general_office", task=task_text))
        return task.task_id

    # ------------------------------------------------------------------
    # Pending → running → done
    # ------------------------------------------------------------------

    def test_task_state_machine_pending_to_done(self) -> None:
        from secnano.runtime_db import claim_task, get_task, mark_done, mark_running

        task_id = self._submit("pending to done")
        task = asyncio.run(get_task(self.paths, task_id))
        self.assertEqual(task.status, "pending")

        ok = asyncio.run(claim_task(self.paths, task_id, "worker-test"))
        self.assertTrue(ok)

        asyncio.run(mark_running(self.paths, task_id, "worker-test"))
        task = asyncio.run(get_task(self.paths, task_id))
        self.assertEqual(task.status, "running")
        self.assertIsNotNone(task.started_at)

        asyncio.run(mark_done(self.paths, task_id, result={"output": "success"}))
        task = asyncio.run(get_task(self.paths, task_id))
        self.assertEqual(task.status, "done")
        self.assertIsNotNone(task.finished_at)
        self.assertEqual(task.result["output"], "success")

    # ------------------------------------------------------------------
    # Pending → running → failed
    # ------------------------------------------------------------------

    def test_task_state_machine_pending_to_failed(self) -> None:
        from secnano.runtime_db import claim_task, get_task, mark_failed, mark_running

        task_id = self._submit("pending to failed")
        asyncio.run(claim_task(self.paths, task_id, "worker-test"))
        asyncio.run(mark_running(self.paths, task_id, "worker-test"))
        asyncio.run(mark_failed(self.paths, task_id, error="execution error"))
        task = asyncio.run(get_task(self.paths, task_id))
        self.assertEqual(task.status, "failed")
        self.assertEqual(task.error, "execution error")
        self.assertIsNotNone(task.finished_at)

    # ------------------------------------------------------------------
    # Timeout state
    # ------------------------------------------------------------------

    def test_task_mark_timeout_with_detail(self) -> None:
        from secnano.runtime_db import get_task, mark_timeout

        task_id = self._submit("timeout task")
        error_detail = {"pid": 99999, "duration_ms": 60000, "last_output": "timeout output"}
        asyncio.run(mark_timeout(self.paths, task_id, error_detail))
        task = asyncio.run(get_task(self.paths, task_id))
        self.assertEqual(task.status, "timeout")
        detail = json.loads(task.error)
        self.assertEqual(detail["pid"], 99999)
        self.assertEqual(detail["duration_ms"], 60000)
        self.assertEqual(detail["last_output"], "timeout output")

    # ------------------------------------------------------------------
    # Pause / Resume / Cancel
    # ------------------------------------------------------------------

    def test_pause_resume_cancel_flow(self) -> None:
        from secnano.runtime_db import get_task, mark_cancelled, mark_paused, mark_resumed

        task_id = self._submit("lifecycle task")

        asyncio.run(mark_paused(self.paths, task_id))
        task = asyncio.run(get_task(self.paths, task_id))
        self.assertEqual(task.status, "paused")

        asyncio.run(mark_resumed(self.paths, task_id))
        task = asyncio.run(get_task(self.paths, task_id))
        self.assertEqual(task.status, "pending")

        asyncio.run(mark_cancelled(self.paths, task_id))
        task = asyncio.run(get_task(self.paths, task_id))
        self.assertEqual(task.status, "cancelled")

    # ------------------------------------------------------------------
    # Retry: create new task preserving old
    # ------------------------------------------------------------------

    def test_retry_creates_new_task_id(self) -> None:
        from secnano.runtime_db import create_task, get_task, mark_failed

        original = asyncio.run(
            create_task(self.paths, role="general_office", task="original task")
        )
        asyncio.run(mark_failed(self.paths, original.task_id, error="first attempt failed"))

        retried = asyncio.run(
            create_task(
                self.paths,
                role=original.role,
                task=original.payload["task"],
                namespace=original.namespace,
            )
        )
        self.assertNotEqual(original.task_id, retried.task_id)
        self.assertEqual(retried.status, "pending")

        # Original task still in DB with failed status
        original_check = asyncio.run(get_task(self.paths, original.task_id))
        self.assertEqual(original_check.status, "failed")

    # ------------------------------------------------------------------
    # Run logs
    # ------------------------------------------------------------------

    def test_run_logs_multiple_attempts(self) -> None:
        from secnano.runtime_db import append_run_log, get_run_logs

        task_id = self._submit("logged task")

        asyncio.run(
            append_run_log(
                self.paths,
                task_id=task_id,
                attempt_no=1,
                worker_id="worker-A",
                status="failed",
                duration_ms=500,
                error_text="first attempt failed",
                result=None,
            )
        )
        asyncio.run(
            append_run_log(
                self.paths,
                task_id=task_id,
                attempt_no=2,
                worker_id="worker-B",
                status="done",
                duration_ms=1000,
                error_text=None,
                result={"summary": "ok"},
            )
        )
        logs = asyncio.run(get_run_logs(self.paths, task_id))
        self.assertEqual(len(logs), 2)
        self.assertEqual(logs[0]["attempt_no"], 1)
        self.assertEqual(logs[0]["status"], "failed")
        self.assertEqual(logs[1]["attempt_no"], 2)
        self.assertEqual(logs[1]["status"], "done")

    # ------------------------------------------------------------------
    # claim_task atomicity (concurrent)
    # ------------------------------------------------------------------

    def test_claim_task_concurrent_atomicity(self) -> None:
        import threading
        from secnano.runtime_db import claim_task

        task_id = self._submit("atomic claim task")
        results = []

        def try_claim(worker_id):
            r = asyncio.run(claim_task(self.paths, task_id, worker_id=worker_id))
            results.append(r)

        threads = [threading.Thread(target=try_claim, args=(f"w-{i}",)) for i in range(5)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()

        successes = sum(1 for r in results if r)
        self.assertEqual(successes, 1, f"Expected exactly 1 success, got: {results}")

    # ------------------------------------------------------------------
    # Scheduled task: get_due_tasks
    # ------------------------------------------------------------------

    def test_interval_scheduled_task_shows_as_due(self) -> None:
        from secnano.runtime_db import create_task_with_id, get_due_tasks

        past = (datetime.now(UTC) - timedelta(seconds=30)).isoformat().replace("+00:00", "Z")
        asyncio.run(
            create_task_with_id(
                self.paths,
                task_id="sched_task_001",
                role="general_office",
                task="interval task",
                schedule_type="interval",
                schedule_value="5000",
                next_run_at=past,
            )
        )
        due = asyncio.run(get_due_tasks(self.paths, datetime.now(UTC)))
        ids = [t.task_id for t in due]
        self.assertIn("sched_task_001", ids)

    def test_future_scheduled_task_not_due(self) -> None:
        from secnano.runtime_db import create_task_with_id, get_due_tasks

        future = (datetime.now(UTC) + timedelta(hours=2)).isoformat().replace("+00:00", "Z")
        asyncio.run(
            create_task_with_id(
                self.paths,
                task_id="sched_future_001",
                role="general_office",
                task="future task",
                schedule_type="cron",
                schedule_value="0 2 * * *",
                next_run_at=future,
            )
        )
        due = asyncio.run(get_due_tasks(self.paths, datetime.now(UTC)))
        ids = [t.task_id for t in due]
        self.assertNotIn("sched_future_001", ids)


class TestPhase1CliCommands(unittest.TestCase):
    """CLI-level tests for new Phase 1 commands."""

    def setUp(self) -> None:
        runtime_dir = REPO_ROOT / "runtime"
        if runtime_dir.exists():
            shutil.rmtree(runtime_dir)

    def _run(self, *args: str) -> subprocess.CompletedProcess[str]:
        return subprocess.run(
            [PYTHON, "-m", "secnano", *args],
            cwd=REPO_ROOT,
            text=True,
            capture_output=True,
            check=False,
        )

    def test_tasks_pause_resume_cancel_via_cli(self) -> None:
        submit = self._run(
            "tasks", "submit", "--role", "general_office", "--task", "cli lifecycle test", "--json"
        )
        self.assertEqual(submit.returncode, 0, submit.stderr)
        task_id = json.loads(submit.stdout)["task_id"]

        pause = self._run("tasks", "pause", task_id, "--json")
        self.assertEqual(pause.returncode, 0, pause.stderr)
        self.assertEqual(json.loads(pause.stdout)["status"], "paused")

        resume = self._run("tasks", "resume", task_id, "--json")
        self.assertEqual(resume.returncode, 0, resume.stderr)
        self.assertEqual(json.loads(resume.stdout)["status"], "pending")

        cancel = self._run("tasks", "cancel", task_id, "--json")
        self.assertEqual(cancel.returncode, 0, cancel.stderr)
        self.assertEqual(json.loads(cancel.stdout)["status"], "cancelled")

    def test_tasks_retry_via_cli(self) -> None:
        submit = self._run(
            "tasks", "submit", "--role", "general_office", "--task", "original retry task", "--json"
        )
        self.assertEqual(submit.returncode, 0, submit.stderr)
        original_id = json.loads(submit.stdout)["task_id"]

        retry = self._run("tasks", "retry", original_id, "--json")
        self.assertEqual(retry.returncode, 0, retry.stderr)
        new_task = json.loads(retry.stdout)
        self.assertNotEqual(new_task["task_id"], original_id)
        self.assertEqual(new_task["status"], "pending")

    def test_tasks_logs_via_cli(self) -> None:
        submit = self._run(
            "tasks", "submit", "--role", "general_office", "--task", "logs test task", "--json"
        )
        self.assertEqual(submit.returncode, 0, submit.stderr)
        task_id = json.loads(submit.stdout)["task_id"]

        # logs with no entries
        logs = self._run("tasks", "logs", task_id, "--json")
        self.assertEqual(logs.returncode, 0, logs.stderr)
        self.assertEqual(json.loads(logs.stdout), [])

    def test_tasks_pause_nonexistent_returns_1(self) -> None:
        result = self._run("tasks", "pause", "task_nonexistent_xyz", "--json")
        self.assertEqual(result.returncode, 1)


if __name__ == "__main__":
    unittest.main()
