import json
import shutil
import subprocess
import unittest
from pathlib import Path


class IntegrationChainTests(unittest.TestCase):
    def setUp(self):
        self.repo = Path(__file__).resolve().parents[2]
        self.runtime = self.repo / "runtime"
        shutil.rmtree(self.runtime, ignore_errors=True)

    def tearDown(self):
        shutil.rmtree(self.runtime, ignore_errors=True)

    def test_delegate_writes_archive_and_prints_reply(self):
        proc = subprocess.run(
            [
                "python",
                "-m",
                "secnano_v2",
                "delegate",
                "--role",
                "demo",
                "--task",
                "run echo hello",
            ],
            cwd=self.repo,
            capture_output=True,
            text=True,
            check=False,
        )
        self.assertEqual(proc.returncode, 0, msg=proc.stderr)
        self.assertIn("hello", proc.stdout)

        task_files = list((self.runtime / "tasks").glob("*.json"))
        self.assertEqual(len(task_files), 1)
        record = json.loads(task_files[0].read_text(encoding="utf-8"))
        self.assertIn("execution", record)
        self.assertEqual(record["execution"]["tool_name"], "echo")

    def test_missing_role_is_structured_error(self):
        proc = subprocess.run(
            [
                "python",
                "-m",
                "secnano_v2",
                "delegate",
                "--role",
                "missing",
                "--task",
                "hello",
            ],
            cwd=self.repo,
            capture_output=True,
            text=True,
            check=False,
        )
        self.assertNotEqual(proc.returncode, 0)
        self.assertIn("[role_load_error]", proc.stderr)
        self.assertNotIn("Traceback", proc.stderr)


if __name__ == "__main__":
    unittest.main()
