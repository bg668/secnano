from __future__ import annotations

import json
import shutil
import subprocess
import unittest
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parent.parent
PYTHON = "python3"


class TasksCliTest(unittest.TestCase):
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

    def test_tasks_submit_and_show_json(self) -> None:
        submit = self._run(
            "tasks",
            "submit",
            "--role",
            "general_office",
            "--task",
            "最小闭环验收",
            "--json",
        )
        self.assertEqual(submit.returncode, 0, submit.stderr)
        submit_payload = json.loads(submit.stdout)
        self.assertEqual(submit_payload["status"], "pending")
        self.assertEqual(submit_payload["role"], "general_office")
        self.assertEqual(submit_payload["payload"]["task"], "最小闭环验收")

        show = self._run("tasks", "show", submit_payload["task_id"], "--json")
        self.assertEqual(show.returncode, 0, show.stderr)
        show_payload = json.loads(show.stdout)
        self.assertEqual(show_payload["task_id"], submit_payload["task_id"])
        self.assertEqual(show_payload["status"], "pending")

    def test_tasks_list_status_filter(self) -> None:
        self._run("tasks", "submit", "--role", "general_office", "--task", "t1")
        self._run("tasks", "submit", "--role", "general_office", "--task", "t2")
        listed = self._run("tasks", "list", "--status", "pending", "--json")
        self.assertEqual(listed.returncode, 0, listed.stderr)
        payload = json.loads(listed.stdout)
        self.assertGreaterEqual(len(payload), 2)
        self.assertTrue(all(item["status"] == "pending" for item in payload))

    def test_tasks_poll_timeout_returns_124(self) -> None:
        submit = self._run("tasks", "submit", "--role", "general_office", "--task", "t", "--json")
        self.assertEqual(submit.returncode, 0, submit.stderr)
        task_id = json.loads(submit.stdout)["task_id"]
        poll = self._run("tasks", "poll", task_id, "--timeout", "0", "--json")
        self.assertEqual(poll.returncode, 124)
        payload = json.loads(poll.stdout)
        self.assertEqual(payload["task_id"], task_id)
        self.assertEqual(payload["status"], "pending")


if __name__ == "__main__":
    unittest.main()
