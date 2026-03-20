from __future__ import annotations

import os
import subprocess
from pathlib import Path
from typing import Callable

_OUTPUT_MAX_CHARS = 10_000

WORKDIR = Path(os.environ.get("SECNANO_WORKDIR", str(Path.cwd()))).resolve()


def safe_path(p: str) -> Path:
    """Resolve path and ensure it is within WORKDIR."""
    resolved = (WORKDIR / p).resolve()
    try:
        resolved.relative_to(WORKDIR)
    except ValueError:
        raise ValueError(f"Path {p!r} escapes the working directory {WORKDIR}")
    return resolved


def handle_read_file(path: str) -> str:
    """Read a file inside WORKDIR and return its contents."""
    target = safe_path(path)
    if not target.is_file():
        raise FileNotFoundError(f"File not found: {path}")
    content = target.read_text(encoding="utf-8", errors="replace")
    if len(content) > _OUTPUT_MAX_CHARS:
        content = content[:_OUTPUT_MAX_CHARS] + "\n... [truncated]"
    return content


def handle_write_file(path: str, content: str) -> str:
    """Write content to a file inside WORKDIR."""
    target = safe_path(path)
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(content, encoding="utf-8")
    return f"Written {len(content)} chars to {path}"


def handle_edit_file(path: str, old_text: str, new_text: str) -> str:
    """Replace the first occurrence of old_text with new_text in a file."""
    target = safe_path(path)
    if not target.is_file():
        raise FileNotFoundError(f"File not found: {path}")
    original = target.read_text(encoding="utf-8")
    if old_text not in original:
        raise ValueError(f"old_text not found in {path}")
    updated = original.replace(old_text, new_text, 1)
    target.write_text(updated, encoding="utf-8")
    return f"Edited {path} (replaced {len(old_text)} chars with {len(new_text)} chars)"


def handle_run_command(command: str, timeout: int = 30) -> str:
    """Run a shell command and return stdout+stderr (truncated to 10000 chars)."""
    try:
        result = subprocess.run(
            command,
            shell=True,
            capture_output=True,
            text=True,
            timeout=timeout,
            cwd=str(WORKDIR),
        )
        output = result.stdout + result.stderr
    except subprocess.TimeoutExpired:
        output = f"Command timed out after {timeout}s: {command}"
    except Exception as exc:
        output = f"Command error: {exc}"

    if len(output) > _OUTPUT_MAX_CHARS:
        output = output[:_OUTPUT_MAX_CHARS] + "\n... [truncated]"
    return output


TOOL_HANDLERS: dict[str, Callable[..., str]] = {
    "read_file": handle_read_file,
    "write_file": handle_write_file,
    "edit_file": handle_edit_file,
    "run_command": handle_run_command,
}

TOOL_SCHEMAS: list[dict] = [
    {
        "name": "read_file",
        "description": "Read the contents of a file within the working directory.",
        "input_schema": {
            "type": "object",
            "properties": {
                "path": {
                    "type": "string",
                    "description": "Relative path to the file (within working directory).",
                }
            },
            "required": ["path"],
        },
    },
    {
        "name": "write_file",
        "description": "Write content to a file within the working directory.",
        "input_schema": {
            "type": "object",
            "properties": {
                "path": {
                    "type": "string",
                    "description": "Relative path to the file (within working directory).",
                },
                "content": {
                    "type": "string",
                    "description": "Content to write to the file.",
                },
            },
            "required": ["path", "content"],
        },
    },
    {
        "name": "edit_file",
        "description": "Replace the first occurrence of old_text with new_text in a file.",
        "input_schema": {
            "type": "object",
            "properties": {
                "path": {
                    "type": "string",
                    "description": "Relative path to the file (within working directory).",
                },
                "old_text": {
                    "type": "string",
                    "description": "Text to search for and replace.",
                },
                "new_text": {
                    "type": "string",
                    "description": "Replacement text.",
                },
            },
            "required": ["path", "old_text", "new_text"],
        },
    },
    {
        "name": "run_command",
        "description": "Run a shell command in the working directory and return its output.",
        "input_schema": {
            "type": "object",
            "properties": {
                "command": {
                    "type": "string",
                    "description": "Shell command to execute.",
                },
                "timeout": {
                    "type": "integer",
                    "description": "Timeout in seconds (default 30).",
                    "default": 30,
                },
            },
            "required": ["command"],
        },
    },
]
