"""
Agent subprocess entry point.

Run as: python -m agent_runner.main

Reads a JSON SubprocessInput from stdin, runs the Anthropic tool-use loop,
and writes SubprocessOutput JSON blocks to stdout wrapped in sentinel markers.
"""

from __future__ import annotations

import json
import os
import sys
import time
import uuid
from pathlib import Path
from typing import Any

OUTPUT_START_MARKER = "---SECNANO_OUTPUT_START---"
OUTPUT_END_MARKER = "---SECNANO_OUTPUT_END---"

IPC_INPUT_DIR_NAME = "input"
IPC_CLOSE_SENTINEL = "_close"
IPC_POLL_INTERVAL_S = 0.5

MAX_HISTORY_MESSAGES = 50  # trim conversation if it grows too large


def write_output(output: dict[str, Any]) -> None:
    """Write a JSON output block wrapped in markers to stdout."""
    print(OUTPUT_START_MARKER, flush=True)
    print(json.dumps(output), flush=True)
    print(OUTPUT_END_MARKER, flush=True)


def write_error(message: str) -> None:
    """Write an error output block and exit with code 1."""
    write_output({"status": "error", "result": None, "error": message})
    sys.exit(1)


# ── Session management ────────────────────────────────────────────────────────

def get_session_file_path(group_folder: str) -> Path:
    """Return the path to the conversation history JSON file."""
    data_dir = Path(os.environ.get("SECNANO_DATA_DIR", "data"))
    return data_dir / "sessions" / group_folder / "history.json"


def load_session(group_folder: str, session_id: str | None) -> list[dict]:
    """Load conversation history from disk if a session exists."""
    if not session_id:
        return []
    session_file = get_session_file_path(group_folder)
    if not session_file.exists():
        return []
    try:
        data = json.loads(session_file.read_text(encoding="utf-8"))
        if isinstance(data, list):
            return data
    except (json.JSONDecodeError, OSError):
        pass
    return []


def save_session(group_folder: str, messages: list[dict]) -> str:
    """Save conversation history to disk and return a session ID."""
    session_file = get_session_file_path(group_folder)
    session_file.parent.mkdir(parents=True, exist_ok=True)

    # Trim to avoid unbounded growth
    if len(messages) > MAX_HISTORY_MESSAGES:
        # Keep the most recent messages; always preserve pairs (user+assistant)
        messages = messages[-MAX_HISTORY_MESSAGES:]

    session_file.write_text(json.dumps(messages, ensure_ascii=False, indent=2), encoding="utf-8")
    return str(uuid.uuid4())


# ── System prompt ─────────────────────────────────────────────────────────────

def build_system_prompt(group_folder: str, is_main: bool, assistant_name: str) -> str:
    """Build the system prompt for the agent."""
    role = "main orchestration agent" if is_main else "group assistant"
    workspace = os.getcwd()

    return (
        f"You are {assistant_name}, an AI assistant acting as a {role}.\n\n"
        f"Current workspace: {workspace}\n"
        f"Group folder: {group_folder}\n\n"
        "You have access to tools that let you read/write files, run bash commands, "
        "search files, and list directories within your workspace. "
        "Use these tools to accomplish tasks.\n\n"
        "When you are done with a task, provide a clear, concise summary of what you did "
        "and any important results. "
        "Wrap any internal reasoning or intermediate steps in <internal>...</internal> tags "
        "so they are not shown to the user.\n\n"
        "Be helpful, accurate, and thorough."
    )


# ── IPC follow-up message reader ──────────────────────────────────────────────

def wait_for_ipc_message(group_folder: str, timeout_s: float = 1800.0) -> str | None:
    """
    Poll the IPC input directory for the next message or close sentinel.

    Returns:
        The message content string if a new message arrived.
        ``None`` if the close sentinel was received or the timeout expired.
    """
    ipc_dir_env = os.environ.get("SECNANO_IPC_DIR")
    if ipc_dir_env:
        ipc_input_dir = Path(ipc_dir_env)
    else:
        data_dir = Path(os.environ.get("SECNANO_DATA_DIR", "data"))
        ipc_input_dir = data_dir / "ipc" / group_folder / IPC_INPUT_DIR_NAME

    deadline = time.monotonic() + timeout_s

    while time.monotonic() < deadline:
        if not ipc_input_dir.exists():
            time.sleep(IPC_POLL_INTERVAL_S)
            continue

        # Check for close sentinel first
        sentinel = ipc_input_dir / IPC_CLOSE_SENTINEL
        if sentinel.exists():
            import contextlib
            with contextlib.suppress(OSError):
                sentinel.unlink(missing_ok=True)
            return None

        # Find the earliest message file (sorted by filename = timestamp prefix)
        json_files = sorted(
            (f for f in ipc_input_dir.iterdir() if f.suffix == ".json" and f.is_file()),
            key=lambda p: p.name,
        )

        if json_files:
            msg_file = json_files[0]
            try:
                data = json.loads(msg_file.read_text(encoding="utf-8"))
                content = data.get("content", "")
                msg_file.unlink(missing_ok=True)
                return content
            except (json.JSONDecodeError, OSError):
                import contextlib
                with contextlib.suppress(OSError):
                    msg_file.unlink(missing_ok=True)

        time.sleep(IPC_POLL_INTERVAL_S)

    return None  # Timeout


# ── Main agent loop ───────────────────────────────────────────────────────────

def main() -> None:
    # 1. Read input from stdin
    try:
        stdin_data = sys.stdin.read()
        container_input: dict[str, Any] = json.loads(stdin_data)
    except (json.JSONDecodeError, OSError) as exc:
        write_error(f"Failed to read/parse stdin: {exc}")
        return

    # 2. Extract parameters
    prompt: str = container_input.get("prompt", "")
    session_id: str | None = container_input.get("session_id")
    group_folder: str = container_input.get("group_folder", "default")
    is_main: bool = container_input.get("is_main", False)
    is_scheduled_task: bool = container_input.get("is_scheduled_task", False)
    assistant_name: str = container_input.get("assistant_name", "Andy")

    if not prompt:
        write_error("No prompt provided")
        return

    # 3. Initialize Anthropic client
    api_key = os.environ.get("ANTHROPIC_API_KEY")
    if not api_key:
        write_error("ANTHROPIC_API_KEY not set")
        return

    try:
        import anthropic
        client = anthropic.Anthropic(api_key=api_key)
    except Exception as exc:
        write_error(f"Failed to initialize Anthropic client: {exc}")
        return

    model = os.environ.get("ANTHROPIC_MODEL", "claude-opus-4-5")

    # 4. Load existing conversation history
    messages: list[dict] = load_session(group_folder, session_id)

    # 5. Build system prompt and tools
    system_prompt = build_system_prompt(group_folder, is_main, assistant_name)

    from agent_runner.tools import TOOLS, execute_tool

    # 6. Prefix scheduled task prompts
    if is_scheduled_task:
        prompt = f"[SCHEDULED TASK - The following message was sent automatically]\n\n{prompt}"

    # 7. Outer loop: handle IPC follow-up messages
    new_session_id: str | None = None

    while True:
        # Add the new user turn
        messages.append({"role": "user", "content": prompt})

        # 8. Inner agent loop: tool_use / end_turn
        result_text: str | None = None

        while True:
            try:
                response = client.messages.create(
                    model=model,
                    max_tokens=8192,
                    system=system_prompt,
                    tools=TOOLS,  # type: ignore[arg-type]
                    messages=messages,
                )
            except Exception as exc:
                write_error(f"Anthropic API error: {exc}")
                return

            # Serialize response content for history (convert objects to dicts)
            content_for_history = []
            for block in response.content:
                if hasattr(block, "model_dump"):
                    content_for_history.append(block.model_dump())
                elif hasattr(block, "__dict__"):
                    content_for_history.append(block.__dict__)
                else:
                    content_for_history.append(str(block))

            messages.append({"role": "assistant", "content": content_for_history})

            if response.stop_reason == "tool_use":
                tool_results = []
                for block in response.content:
                    if hasattr(block, "type") and block.type == "tool_use":
                        tool_result = execute_tool(block.name, block.input, os.getcwd())
                        tool_results.append(
                            {
                                "type": "tool_result",
                                "tool_use_id": block.id,
                                "content": tool_result,
                            }
                        )
                messages.append({"role": "user", "content": tool_results})
                # Continue inner loop

            elif response.stop_reason == "end_turn":
                # Extract text result from response
                for block in response.content:
                    if hasattr(block, "type") and block.type == "text":
                        result_text = block.text
                        break
                break  # Break inner agent loop

            else:
                # Unexpected stop reason
                break

        # Save session after each turn
        new_session_id = save_session(group_folder, messages)

        # Write the turn result (with actual text)
        write_output(
            {
                "status": "success",
                "result": result_text,
                "new_session_id": new_session_id,
            }
        )

        # Write a heartbeat indicating the session is alive (result: None)
        write_output(
            {
                "status": "success",
                "result": None,
                "new_session_id": new_session_id,
            }
        )

        # 9. Wait for the next IPC message or close sentinel
        next_message = wait_for_ipc_message(group_folder)
        if next_message is None:
            break  # Close sentinel or timeout

        prompt = next_message

    # Done


if __name__ == "__main__":
    main()
