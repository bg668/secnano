from __future__ import annotations

import json
import shutil
import subprocess
import unittest
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parent.parent
PYTHON = "python3"
TMP_DIR = Path("/tmp/secnano-tests")


class IpcCliTest(unittest.TestCase):
    def setUp(self) -> None:
        runtime_dir = REPO_ROOT / "runtime"
        if runtime_dir.exists():
            shutil.rmtree(runtime_dir)
        TMP_DIR.mkdir(parents=True, exist_ok=True)

    def _run(self, *args: str) -> subprocess.CompletedProcess[str]:
        return subprocess.run(
            [PYTHON, "-m", "secnano", *args],
            cwd=REPO_ROOT,
            text=True,
            capture_output=True,
            check=False,
        )

    def test_ipc_write_task_and_watch_imports_task(self) -> None:
        write_res = self._run(
            "ipc",
            "write-task",
            "--role",
            "general_office",
            "--task",
            "通过 IPC 写入",
            "--namespace",
            "main",
            "--json",
        )
        self.assertEqual(write_res.returncode, 0, write_res.stderr)
        write_payload = json.loads(write_res.stdout)
        task_id = write_payload["task_id"]
        self.assertTrue(write_payload["file"].endswith(f"{task_id}.json"))

        watch_res = self._run("ipc", "watch", "--namespace", "main", "--json")
        self.assertEqual(watch_res.returncode, 0, watch_res.stderr)
        watch_payload = json.loads(watch_res.stdout)
        self.assertEqual(len(watch_payload), 1)
        self.assertTrue(watch_payload[0]["processed"])
        self.assertEqual(watch_payload[0]["task_id"], task_id)

        show_res = self._run("tasks", "show", task_id, "--json")
        self.assertEqual(show_res.returncode, 0, show_res.stderr)
        show_payload = json.loads(show_res.stdout)
        self.assertEqual(show_payload["payload"]["task"], "通过 IPC 写入")
        self.assertEqual(show_payload["namespace"], "main")

    def test_ipc_watch_denied_namespace_archives_error(self) -> None:
        deny_request = {
            "version": "v1",
            "request_id": "req_denied",
            "task_id": "task_denied_001",
            "namespace": "dev",
            "role": "general_office",
            "created_at": "2026-03-20T00:00:00Z",
            "payload": {"task": "越权任务"},
            "options": {"max_retries": 0},
        }
        denied_file = TMP_DIR / "tmp-denied.json"
        denied_file.write_text(json.dumps(deny_request, ensure_ascii=False), encoding="utf-8")
        write_res = self._run(
            "ipc",
            "write-task",
            "--file",
            str(denied_file.resolve()),
            "--json",
        )
        self.assertEqual(write_res.returncode, 0, write_res.stderr)
        denied_file.unlink(missing_ok=True)

        watch_res = self._run("ipc", "watch", "--namespace", "dev", "--json")
        self.assertEqual(watch_res.returncode, 0, watch_res.stderr)
        payload = json.loads(watch_res.stdout)
        self.assertEqual(len(payload), 1)
        self.assertFalse(payload[0]["processed"])
        self.assertEqual(payload[0]["error"], "auth_denied")

        errors_dir = REPO_ROOT / "runtime" / "ipc" / "errors"
        self.assertTrue(errors_dir.exists())
        error_files = sorted(errors_dir.glob("*.json"))
        self.assertGreaterEqual(len(error_files), 1)
        error_payload = json.loads(error_files[-1].read_text(encoding="utf-8"))
        self.assertEqual(error_payload["error_code"], "IPC_AUTH_DENIED")
        self.assertEqual(error_payload["namespace"], "dev")

        show_res = self._run("tasks", "show", "task_denied_001", "--json")
        self.assertEqual(show_res.returncode, 1)


if __name__ == "__main__":
    unittest.main()
