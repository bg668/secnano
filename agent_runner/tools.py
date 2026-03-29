"""
Tool implementations for the agent loop.

Each tool is callable by the Anthropic model via the tool_use mechanism.
All filesystem operations are sandboxed relative to the group workspace (cwd).
"""

from __future__ import annotations

import json
import os
import re
import subprocess
import time
import uuid
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

# ── Tool definitions (Anthropic schema) ──────────────────────────────────────

TOOLS: list[dict] = [
    {
        "name": "bash",
        "description": (
            "Execute a bash command in the group workspace and return its output. "
            "Commands run with the group folder as the working directory."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "command": {
                    "type": "string",
                    "description": "The bash command to execute.",
                },
                "timeout": {
                    "type": "integer",
                    "description": "Timeout in seconds (default: 30, max: 120).",
                },
            },
            "required": ["command"],
        },
    },
    {
        "name": "register_group",
        "description": (
            "Request host-side registration for a new group via IPC task file. "
            "Only host-authorized main groups can complete this request."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "jid": {
                    "type": "string",
                    "description": "The target chat JID to register.",
                },
                "name": {
                    "type": "string",
                    "description": "Human-friendly group name.",
                },
                "folder": {
                    "type": "string",
                    "description": "Workspace folder slug for this group.",
                },
                "trigger": {
                    "type": "string",
                    "description": "Mention trigger text, e.g. '@Andy'. Defaults to the assistant name.",
                },
                "requires_trigger": {
                    "type": "boolean",
                    "description": "Whether mentions are required to trigger replies.",
                },
            },
            "required": ["jid", "name", "folder"],
        },
    },
    {
        "name": "read_file",
        "description": "Read the contents of a file relative to the workspace.",
        "input_schema": {
            "type": "object",
            "properties": {
                "path": {
                    "type": "string",
                    "description": "Path to the file (relative to workspace or absolute).",
                },
            },
            "required": ["path"],
        },
    },
    {
        "name": "write_file",
        "description": (
            "Write content to a file (creates or overwrites). Path is relative to workspace."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "path": {
                    "type": "string",
                    "description": "Path to the file.",
                },
                "content": {
                    "type": "string",
                    "description": "Content to write.",
                },
            },
            "required": ["path", "content"],
        },
    },
    {
        "name": "edit_file",
        "description": "Replace the first occurrence of a string in a file.",
        "input_schema": {
            "type": "object",
            "properties": {
                "path": {
                    "type": "string",
                    "description": "Path to the file.",
                },
                "old_str": {
                    "type": "string",
                    "description": "The string to find and replace.",
                },
                "new_str": {
                    "type": "string",
                    "description": "The replacement string.",
                },
            },
            "required": ["path", "old_str", "new_str"],
        },
    },
    {
        "name": "glob",
        "description": "Find files matching a glob pattern within the workspace.",
        "input_schema": {
            "type": "object",
            "properties": {
                "pattern": {
                    "type": "string",
                    "description": "Glob pattern, e.g. '**/*.py' or 'src/*.txt'.",
                },
            },
            "required": ["pattern"],
        },
    },
    {
        "name": "grep",
        "description": "Search for a regex pattern in files within the workspace.",
        "input_schema": {
            "type": "object",
            "properties": {
                "pattern": {
                    "type": "string",
                    "description": "Regex pattern to search for.",
                },
                "path": {
                    "type": "string",
                    "description": "File or directory to search (defaults to workspace root).",
                },
                "case_insensitive": {
                    "type": "boolean",
                    "description": "Whether to ignore case (default: false).",
                },
            },
            "required": ["pattern"],
        },
    },
    {
        "name": "list_directory",
        "description": "List files and directories at a given path within the workspace.",
        "input_schema": {
            "type": "object",
            "properties": {
                "path": {
                    "type": "string",
                    "description": "Directory path (defaults to workspace root).",
                },
            },
            "required": [],
        },
    },
]


# ── Security helpers ──────────────────────────────────────────────────────────

def _safe_path(requested: str, cwd: str) -> Path:
    """
    Resolve *requested* relative to *cwd* and ensure it stays within *cwd*.

    Raises ``ValueError`` on path-traversal attempts.
    """
    base = Path(cwd).resolve()
    candidate = (base / requested).resolve()
    # Allow exact match or paths under the base
    if candidate != base and not str(candidate).startswith(str(base) + os.sep):
        raise ValueError(
            f"Path traversal denied: {requested!r} escapes workspace {cwd!r}"
        )
    return candidate


def _resolve_tasks_dir() -> Path:
    tasks_dir = os.environ.get("SECNANO_TASKS_DIR")
    if tasks_dir:
        return Path(tasks_dir)

    data_dir = os.environ.get("SECNANO_DATA_DIR")
    group_folder = os.environ.get("SECNANO_GROUP_FOLDER")
    if not data_dir or not group_folder:
        raise ValueError("SECNANO_TASKS_DIR (or DATA_DIR + GROUP_FOLDER) is not configured")
    return Path(data_dir) / "ipc" / group_folder / "tasks"


def _write_task_request(task_data: dict[str, Any]) -> str:
    tasks_dir = _resolve_tasks_dir()
    tasks_dir.mkdir(parents=True, exist_ok=True)

    filename = f"{int(time.time() * 1000)}_{uuid.uuid4().hex[:8]}.json"
    final_path = tasks_dir / filename
    temp_path = tasks_dir / f".{filename}.tmp"
    temp_path.write_text(json.dumps(task_data, ensure_ascii=False), encoding="utf-8")
    temp_path.replace(final_path)
    return filename


# ── Tool implementations ──────────────────────────────────────────────────────

def execute_bash(command: str, cwd: str, timeout: int = 30) -> str:
    """Run *command* in a shell within *cwd* and return combined stdout/stderr."""
    timeout = min(timeout, 120)
    try:
        result = subprocess.run(
            command,
            shell=True,
            cwd=cwd,
            capture_output=True,
            text=True,
            timeout=timeout,
        )
        output = result.stdout
        if result.stderr:
            output += "\n[stderr]\n" + result.stderr
        if result.returncode != 0:
            output += f"\n[exit code: {result.returncode}]"
        return output.strip() or "(no output)"
    except subprocess.TimeoutExpired:
        return f"[error] Command timed out after {timeout}s"
    except Exception as exc:
        return f"[error] {exc}"


def register_group(
    jid: str,
    name: str,
    folder: str,
    trigger: str | None = None,
    requires_trigger: bool | None = None,
) -> str:
    """Write a register_group IPC task request for host-side processing."""
    jid = (jid or "").strip()
    name = (name or "").strip()
    folder = (folder or "").strip()
    assistant_name = os.environ.get("ASSISTANT_NAME", "Andy").strip() or "Andy"
    trigger = (trigger or f"@{assistant_name}").strip()

    if not jid or not name or not folder or not trigger:
        return "[error] jid, name, folder and trigger must be non-empty"

    if not re.match(r"^[A-Za-z0-9][A-Za-z0-9_-]{0,63}$", folder):
        return "[error] folder must match ^[A-Za-z0-9][A-Za-z0-9_-]{0,63}$"

    payload: dict[str, Any] = {
        "type": "register_group",
        "jid": jid,
        "name": name,
        "folder": folder,
        "trigger": trigger,
        "timestamp": datetime.now(UTC).isoformat(),
    }
    if requires_trigger is not None:
        payload["requires_trigger"] = bool(requires_trigger)

    try:
        filename = _write_task_request(payload)
    except Exception as exc:
        return f"[error] Failed to write IPC task: {exc}"

    return f"register_group request queued: {filename}"


def read_file(path: str, cwd: str) -> str:
    """Read and return the contents of *path*."""
    try:
        safe = _safe_path(path, cwd)
        return safe.read_text(encoding="utf-8", errors="replace")
    except ValueError as exc:
        return f"[error] {exc}"
    except FileNotFoundError:
        return f"[error] File not found: {path}"
    except Exception as exc:
        return f"[error] {exc}"


def write_file(path: str, content: str, cwd: str) -> str:
    """Write *content* to *path*. Creates parent directories as needed."""
    try:
        safe = _safe_path(path, cwd)
        safe.parent.mkdir(parents=True, exist_ok=True)
        safe.write_text(content, encoding="utf-8")
        return f"Written {len(content)} bytes to {path}"
    except ValueError as exc:
        return f"[error] {exc}"
    except Exception as exc:
        return f"[error] {exc}"


def edit_file(path: str, old_str: str, new_str: str, cwd: str) -> str:
    """Replace the first occurrence of *old_str* with *new_str* in *path*."""
    try:
        safe = _safe_path(path, cwd)
        original = safe.read_text(encoding="utf-8")
        if old_str not in original:
            return f"[error] String not found in {path}"
        updated = original.replace(old_str, new_str, 1)
        safe.write_text(updated, encoding="utf-8")
        return f"Replaced 1 occurrence in {path}"
    except ValueError as exc:
        return f"[error] {exc}"
    except FileNotFoundError:
        return f"[error] File not found: {path}"
    except Exception as exc:
        return f"[error] {exc}"


def glob_files(pattern: str, cwd: str) -> str:
    """Return newline-separated paths matching *pattern* within *cwd*."""
    try:
        base = Path(cwd).resolve()
        matches = list(base.glob(pattern))
        if not matches:
            return "(no matches)"
        return "\n".join(str(m.relative_to(base)) for m in sorted(matches))
    except Exception as exc:
        return f"[error] {exc}"


def grep_files(
    pattern: str,
    path: str | None,
    cwd: str,
    case_insensitive: bool = False,
) -> str:
    """Search for *pattern* in files under *path* (default: workspace root)."""
    try:
        base = Path(cwd).resolve()
        search_root = _safe_path(path, cwd) if path else base

        flags = re.IGNORECASE if case_insensitive else 0
        compiled = re.compile(pattern, flags)

        results: list[str] = []
        if search_root.is_file():
            _grep_file(search_root, compiled, base, results)
        else:
            for f in sorted(search_root.rglob("*")):
                if f.is_file():
                    _grep_file(f, compiled, base, results)

        return "\n".join(results) if results else "(no matches)"
    except ValueError as exc:
        return f"[error] {exc}"
    except re.error as exc:
        return f"[error] Invalid regex: {exc}"
    except Exception as exc:
        return f"[error] {exc}"


def _grep_file(
    file_path: Path,
    pattern: re.Pattern,
    base: Path,
    results: list[str],
) -> None:
    try:
        text = file_path.read_text(encoding="utf-8", errors="replace")
    except OSError:
        return
    rel = file_path.relative_to(base)
    for lineno, line in enumerate(text.splitlines(), start=1):
        if pattern.search(line):
            results.append(f"{rel}:{lineno}: {line}")
            if len(results) >= 200:  # cap output
                results.append("... (output truncated)")
                raise StopIteration


def list_directory(path: str | None, cwd: str) -> str:
    """List entries in *path* (default: workspace root)."""
    try:
        base = Path(cwd).resolve()
        target = _safe_path(path, cwd) if path else base
        if not target.is_dir():
            return f"[error] Not a directory: {path}"
        entries = sorted(target.iterdir(), key=lambda p: (p.is_file(), p.name))
        lines = []
        for entry in entries:
            suffix = "/" if entry.is_dir() else ""
            lines.append(f"{entry.name}{suffix}")
        return "\n".join(lines) if lines else "(empty directory)"
    except ValueError as exc:
        return f"[error] {exc}"
    except Exception as exc:
        return f"[error] {exc}"


# ── Dispatcher ────────────────────────────────────────────────────────────────

def execute_tool(name: str, input_data: dict[str, Any], cwd: str) -> str:
    """Dispatch a tool call by name and return its string result."""
    try:
        if name == "bash":
            return execute_bash(
                input_data["command"],
                cwd,
                input_data.get("timeout", 30),
            )
        elif name == "register_group":
            return register_group(
                jid=input_data["jid"],
                name=input_data["name"],
                folder=input_data["folder"],
                trigger=input_data.get("trigger"),
                requires_trigger=input_data.get("requires_trigger"),
            )
        elif name == "read_file":
            return read_file(input_data["path"], cwd)
        elif name == "write_file":
            return write_file(input_data["path"], input_data["content"], cwd)
        elif name == "edit_file":
            return edit_file(
                input_data["path"],
                input_data["old_str"],
                input_data["new_str"],
                cwd,
            )
        elif name == "glob":
            return glob_files(input_data["pattern"], cwd)
        elif name == "grep":
            return grep_files(
                input_data["pattern"],
                input_data.get("path"),
                cwd,
                input_data.get("case_insensitive", False),
            )
        elif name == "list_directory":
            return list_directory(input_data.get("path"), cwd)
        else:
            return f"[error] Unknown tool: {name}"
    except KeyError as exc:
        return f"[error] Missing required parameter: {exc}"
    except StopIteration:
        # Raised internally by _grep_file when result cap is hit
        return "(output truncated at 200 matches)"
    except Exception as exc:
        return f"[error] Tool execution failed: {exc}"
