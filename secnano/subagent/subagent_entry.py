from __future__ import annotations

"""Sub-agent entry point.

Loaded by WorkerPool as a subprocess via: python3 -m secnano._subagent <base64_task_json>

Flow:
1. Decode task JSON from base64 argv[1] (contains task_id, role, payload, db_path)
2. Build system prompt from roles/{role}/ROLE.md + SOUL.md
3. Build initial user message from payload["task"]
4. Call run_agent_loop(messages, TOOL_SCHEMAS, TOOL_HANDLERS, system)
5. mark_done(result={"summary": final_text}) or mark_failed(error)
6. Exit 0 (success) / 1 (failure)
"""

import base64
import json
import sys
from pathlib import Path


def _load_role_system_prompt(root_dir: Path, role: str) -> str:
    """Load ROLE.md and SOUL.md for the given role."""
    role_dir = root_dir / "roles" / role
    parts: list[str] = []
    for filename in ("ROLE.md", "SOUL.md"):
        candidate = role_dir / filename
        if candidate.is_file():
            parts.append(candidate.read_text(encoding="utf-8").strip())
    if not parts:
        parts.append(f"You are a {role} agent. Complete the task provided by the user.")
    return "\n\n".join(parts)


def main(argv: list[str] | None = None) -> int:
    args = argv if argv is not None else sys.argv[1:]
    if not args:
        print("Usage: python3 -m secnano._subagent <base64_task_json>", file=sys.stderr)
        return 1

    try:
        task_json = base64.b64decode(args[0]).decode("utf-8")
        task_data = json.loads(task_json)
    except Exception as exc:
        print(f"Failed to decode task JSON: {exc}", file=sys.stderr)
        return 1

    task_id: str = task_data.get("task_id", "")
    role: str = task_data.get("role", "general_office")
    payload: dict = task_data.get("payload", {})
    db_path_str: str | None = task_data.get("db_path")

    if not task_id:
        print("task_id missing from task data", file=sys.stderr)
        return 1

    # Reconstruct paths using db_path from task data
    from secnano.paths import ProjectPaths

    if db_path_str:
        db_path = Path(db_path_str)
        root_dir = db_path.parent.parent.parent  # runtime/db/secnano.sqlite3 -> repo root
        paths = ProjectPaths(
            root_dir=root_dir,
            runtime_dir=root_dir / "runtime",
            db_dir=root_dir / "runtime" / "db",
            db_path=db_path,
            ipc_dir=root_dir / "runtime" / "ipc",
            ipc_errors_dir=root_dir / "runtime" / "ipc" / "errors",
        )
    else:
        paths = ProjectPaths.discover()

    from secnano.runtime_db import mark_done, mark_failed, mark_running

    worker_id = task_data.get("worker_id", "subagent")
    mark_running(paths, task_id, worker_id)

    try:
        from secnano.agent_loop import run_agent_loop
        from secnano.tools.dispatch import TOOL_HANDLERS, TOOL_SCHEMAS

        system = _load_role_system_prompt(paths.root_dir, role)
        task_description = payload.get("task", "Complete the assigned task.")
        messages = [{"role": "user", "content": task_description}]

        final_text = run_agent_loop(
            messages=messages,
            tools=TOOL_SCHEMAS,
            tool_handlers=TOOL_HANDLERS,
            system=system,
            max_rounds=50,
        )

        mark_done(paths, task_id, result={"summary": final_text})
        return 0

    except Exception as exc:
        error_msg = str(exc)
        try:
            mark_failed(paths, task_id, error=error_msg)
        except Exception:
            pass
        print(f"Subagent error for task {task_id}: {error_msg}", file=sys.stderr)
        return 1
