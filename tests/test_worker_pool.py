from __future__ import annotations

import shutil
import unittest
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent


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


class TestRuntimeDbNewFunctions(unittest.TestCase):
    def setUp(self) -> None:
        self._tmp = Path("/tmp/secnano-worker-test")
        if self._tmp.exists():
            shutil.rmtree(self._tmp)
        self._tmp.mkdir(parents=True, exist_ok=True)
        self.paths = _make_paths(self._tmp)
        from secnano.runtime_db import init_db

        init_db(self.paths)

    def tearDown(self) -> None:
        if self._tmp.exists():
            shutil.rmtree(self._tmp)

    def _submit(self, task_text: str = "test task") -> str:
        from secnano.runtime_db import create_task

        task = create_task(self.paths, role="general_office", task=task_text)
        return task.task_id

    # ------------------------------------------------------------------
    # claim_task atomicity
    # ------------------------------------------------------------------

    def test_claim_task_success(self) -> None:
        from secnano.runtime_db import claim_task, get_task

        task_id = self._submit()
        result = claim_task(self.paths, task_id, worker_id="worker-01")
        self.assertTrue(result)
        task = get_task(self.paths, task_id)
        self.assertEqual(task.status, "claimed")
        self.assertEqual(task.worker_id, "worker-01")

    def test_claim_task_atomicity_only_one_succeeds(self) -> None:
        """Two concurrent claim_task calls on the same task: only one should succeed."""
        from secnano.runtime_db import claim_task

        task_id = self._submit()
        r1 = claim_task(self.paths, task_id, worker_id="worker-A")
        r2 = claim_task(self.paths, task_id, worker_id="worker-B")
        # Exactly one should succeed
        self.assertEqual(r1 + r2, 1, f"Expected exactly one success, got r1={r1}, r2={r2}")

    def test_claim_task_already_claimed_returns_false(self) -> None:
        from secnano.runtime_db import claim_task

        task_id = self._submit()
        claim_task(self.paths, task_id, worker_id="worker-01")
        result = claim_task(self.paths, task_id, worker_id="worker-02")
        self.assertFalse(result)

    # ------------------------------------------------------------------
    # mark_done
    # ------------------------------------------------------------------

    def test_mark_done_sets_status(self) -> None:
        from secnano.runtime_db import get_task, mark_done

        task_id = self._submit()
        mark_done(self.paths, task_id, result={"summary": "all good"})
        task = get_task(self.paths, task_id)
        self.assertEqual(task.status, "done")
        self.assertIsNotNone(task.result)
        self.assertEqual(task.result.get("summary"), "all good")
        self.assertIsNotNone(task.finished_at)

    # ------------------------------------------------------------------
    # mark_failed
    # ------------------------------------------------------------------

    def test_mark_failed_sets_status(self) -> None:
        from secnano.runtime_db import get_task, mark_failed

        task_id = self._submit()
        mark_failed(self.paths, task_id, error="something went wrong")
        task = get_task(self.paths, task_id)
        self.assertEqual(task.status, "failed")
        self.assertEqual(task.error, "something went wrong")
        self.assertIsNotNone(task.finished_at)

    # ------------------------------------------------------------------
    # list_pending_tasks
    # ------------------------------------------------------------------

    def test_list_pending_tasks_returns_only_pending(self) -> None:
        from secnano.runtime_db import list_pending_tasks, mark_done

        t1 = self._submit("task 1")
        t2 = self._submit("task 2")
        t3 = self._submit("task 3")

        mark_done(self.paths, t3, result={"summary": "done"})

        pending = list_pending_tasks(self.paths, limit=10)
        pending_ids = {t.task_id for t in pending}
        self.assertIn(t1, pending_ids)
        self.assertIn(t2, pending_ids)
        self.assertNotIn(t3, pending_ids)
        self.assertTrue(all(t.status in ("pending", "queued") for t in pending))

    def test_list_pending_tasks_excludes_failed(self) -> None:
        from secnano.runtime_db import list_pending_tasks, mark_failed

        t1 = self._submit("task 1")
        t2 = self._submit("task 2")
        mark_failed(self.paths, t2, error="error")

        pending = list_pending_tasks(self.paths, limit=10)
        pending_ids = {t.task_id for t in pending}
        self.assertIn(t1, pending_ids)
        self.assertNotIn(t2, pending_ids)

    # ------------------------------------------------------------------
    # append_run_log
    # ------------------------------------------------------------------

    def test_append_run_log_succeeds(self) -> None:
        from secnano.runtime_db import append_run_log

        task_id = self._submit()
        # Should not raise
        append_run_log(
            self.paths,
            task_id=task_id,
            attempt_no=1,
            worker_id="worker-01",
            status="done",
            duration_ms=1234,
            error_text=None,
            result={"summary": "ok"},
        )

    # ------------------------------------------------------------------
    # update_task_status
    # ------------------------------------------------------------------

    def test_update_task_status(self) -> None:
        from secnano.runtime_db import get_task, update_task_status

        task_id = self._submit()
        update_task_status(self.paths, task_id, "queued")
        task = get_task(self.paths, task_id)
        self.assertEqual(task.status, "queued")


if __name__ == "__main__":
    unittest.main()
