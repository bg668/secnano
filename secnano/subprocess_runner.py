"""
subprocess.Popen-based agent spawner.

Replaces Docker container execution from nanoclaw with a Python subprocess
that runs agent_runner.main. Communication uses stdin/stdout with markers.
"""

from __future__ import annotations

import asyncio
import json
import os
import sys
from typing import Awaitable, Callable, Optional

from secnano.config import DATA_DIR, GROUPS_DIR, PROJECT_ROOT, SUBPROCESS_TIMEOUT
from secnano.logger import get_logger
from secnano.types import RegisteredGroup, SubprocessInput, SubprocessOutput

log = get_logger("subprocess_runner")

OUTPUT_START_MARKER = "---SECNANO_OUTPUT_START---"
OUTPUT_END_MARKER = "---SECNANO_OUTPUT_END---"


def _build_env(group_folder: str) -> dict[str, str]:
    """Build the environment variables for the agent subprocess."""
    env = os.environ.copy()
    # Ensure the agent_runner package is importable
    env["PYTHONPATH"] = str(PROJECT_ROOT)
    env["SECNANO_GROUP_FOLDER"] = group_folder
    env["SECNANO_GROUPS_DIR"] = str(GROUPS_DIR)
    env["SECNANO_DATA_DIR"] = str(DATA_DIR)
    env["SECNANO_IPC_DIR"] = str(DATA_DIR / "ipc" / group_folder / "input")
    # ANTHROPIC_API_KEY is inherited from os.environ.copy() above
    return env


async def _read_until_marker(stream: asyncio.StreamReader, marker: str) -> str:
    """Read lines from *stream* until *marker* is found, return accumulated text."""
    lines: list[str] = []
    while True:
        try:
            line_bytes = await asyncio.wait_for(stream.readline(), timeout=5.0)
        except asyncio.TimeoutError:
            break
        if not line_bytes:
            break
        line = line_bytes.decode("utf-8", errors="replace").rstrip("\n")
        if line == marker:
            break
        lines.append(line)
    return "\n".join(lines)


async def _collect_output(
    stdout: asyncio.StreamReader,
    on_output: Optional[Callable[[SubprocessOutput], Awaitable[None]]],
) -> list[SubprocessOutput]:
    """Read all OUTPUT_START/END marker-wrapped JSON blocks from stdout."""
    outputs: list[SubprocessOutput] = []

    while True:
        try:
            line_bytes = await asyncio.wait_for(stdout.readline(), timeout=2.0)
        except asyncio.TimeoutError:
            break
        if not line_bytes:
            break

        line = line_bytes.decode("utf-8", errors="replace").rstrip("\n")

        if line == OUTPUT_START_MARKER:
            json_line_bytes = await stdout.readline()
            if not json_line_bytes:
                break
            json_line = json_line_bytes.decode("utf-8", errors="replace").rstrip("\n")
            end_line_bytes = await stdout.readline()
            if not end_line_bytes:
                break
            end_line = end_line_bytes.decode("utf-8", errors="replace").rstrip("\n")

            if end_line == OUTPUT_END_MARKER:
                try:
                    data = json.loads(json_line)
                    output = SubprocessOutput(
                        status=data.get("status", "error"),
                        result=data.get("result"),
                        new_session_id=data.get("new_session_id"),
                        error=data.get("error"),
                    )
                    outputs.append(output)
                    if on_output:
                        await on_output(output)
                except json.JSONDecodeError as exc:
                    log.error("Failed to parse subprocess output JSON", error=str(exc))

    return outputs


async def run_subprocess_agent(
    group: RegisteredGroup,
    input_data: SubprocessInput,
    on_process: Callable[[asyncio.subprocess.Process, str, str], None],
    on_output: Optional[Callable[[SubprocessOutput], Awaitable[None]]] = None,
) -> SubprocessOutput:
    """
    Spawn an agent subprocess and collect its output.

    Args:
        group: The registered group configuration.
        input_data: The input to pass to the agent via stdin.
        on_process: Called with (process, subprocess_name, group_folder) after spawn.
        on_output: Optional callback invoked for each output block (including
                   intermediate null-result heartbeats).

    Returns:
        The final ``SubprocessOutput`` from the subprocess, or an error output.
    """
    group_folder = group.folder
    timeout = (
        group.subprocess_config.timeout
        if group.subprocess_config and group.subprocess_config.timeout
        else SUBPROCESS_TIMEOUT
    )

    # Resolve the working directory for the subprocess
    workspace_dir = GROUPS_DIR / group_folder
    workspace_dir.mkdir(parents=True, exist_ok=True)

    env = _build_env(group_folder)
    stdin_payload = json.dumps(
        {
            "prompt": input_data.prompt,
            "session_id": input_data.session_id,
            "group_folder": input_data.group_folder,
            "chat_jid": input_data.chat_jid,
            "is_main": input_data.is_main,
            "is_scheduled_task": input_data.is_scheduled_task,
            "assistant_name": input_data.assistant_name,
        }
    ).encode("utf-8")

    subprocess_name = f"agent-{group_folder}"
    log.info("Spawning agent subprocess", name=subprocess_name, folder=group_folder)

    try:
        proc = await asyncio.create_subprocess_exec(
            sys.executable,
            "-m",
            "agent_runner.main",
            stdin=asyncio.subprocess.PIPE,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
            cwd=str(workspace_dir),
            env=env,
        )
    except Exception as exc:
        log.error("Failed to spawn agent subprocess", error=str(exc))
        return SubprocessOutput(status="error", result=None, error=str(exc))

    on_process(proc, subprocess_name, group_folder)

    # Send input via stdin then close it
    assert proc.stdin is not None
    assert proc.stdout is not None
    assert proc.stderr is not None

    try:
        proc.stdin.write(stdin_payload)
        await proc.stdin.drain()
        proc.stdin.close()
    except Exception as exc:
        log.error("Failed to write subprocess stdin", error=str(exc))
        return SubprocessOutput(status="error", result=None, error=str(exc))

    # Collect output and stderr concurrently
    stderr_chunks: list[str] = []

    async def _drain_stderr() -> None:
        while True:
            chunk = await proc.stderr.read(4096)
            if not chunk:
                break
            stderr_chunks.append(chunk.decode("utf-8", errors="replace"))

    try:
        outputs, _ = await asyncio.wait_for(
            asyncio.gather(
                _collect_output(proc.stdout, on_output),
                _drain_stderr(),
            ),
            timeout=float(timeout),
        )
    except asyncio.TimeoutError:
        log.error("Subprocess timed out", name=subprocess_name, timeout=timeout)
        proc.kill()
        return SubprocessOutput(
            status="error",
            result=None,
            error=f"Subprocess timed out after {timeout}s",
        )
    except Exception as exc:
        log.error("Error collecting subprocess output", error=str(exc))
        proc.kill()
        return SubprocessOutput(status="error", result=None, error=str(exc))

    # Wait for process to exit
    try:
        await asyncio.wait_for(proc.wait(), timeout=10.0)
    except asyncio.TimeoutError:
        proc.kill()

    if proc.returncode != 0 and stderr_chunks:
        stderr_text = "".join(stderr_chunks)
        log.warning("Subprocess stderr", name=subprocess_name, stderr=stderr_text[:500])

    # Return the last meaningful output (non-null result)
    final: Optional[SubprocessOutput] = None
    for output in reversed(outputs):
        if output.result is not None or output.status == "error":
            final = output
            break

    if final is None:
        if outputs:
            final = outputs[-1]
        else:
            stderr_text = "".join(stderr_chunks)
            final = SubprocessOutput(
                status="error",
                result=None,
                error=f"No output from subprocess. stderr: {stderr_text[:200]}",
            )

    return final
