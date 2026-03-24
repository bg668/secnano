"""
Filesystem-based IPC watcher.

Polls ``data/ipc/{group}/messages/`` and ``data/ipc/{group}/tasks/`` for
new JSON files written by external processes (e.g., channel bridges).
"""

from __future__ import annotations

import asyncio
import json
from pathlib import Path
from typing import Awaitable, Callable, Optional

from secnano.config import DATA_DIR, IPC_POLL_INTERVAL
from secnano.logger import get_logger
from secnano.types import NewMessage, ScheduledTask

log = get_logger("ipc")

_MESSAGES_DIR_NAME = "messages"
_TASKS_DIR_NAME = "tasks"


def _ipc_base(group_folder: str) -> Path:
    return DATA_DIR / "ipc" / group_folder


def _messages_dir(group_folder: str) -> Path:
    return _ipc_base(group_folder) / _MESSAGES_DIR_NAME


def _tasks_dir(group_folder: str) -> Path:
    return _ipc_base(group_folder) / _TASKS_DIR_NAME


async def _poll_directory(
    directory: Path,
    handler: Callable[[Path], Awaitable[None]],
) -> None:
    """Process all ``.json`` files in *directory*, deleting each after handling."""
    if not directory.exists():
        return

    entries = sorted(directory.iterdir(), key=lambda p: p.name)
    for entry in entries:
        if entry.suffix != ".json" or not entry.is_file():
            continue
        try:
            await handler(entry)
        except Exception as exc:
            log.error("IPC handler error", file=str(entry), error=str(exc))
        finally:
            try:
                entry.unlink(missing_ok=True)
            except OSError:
                pass


MessageHandler = Callable[[NewMessage], Awaitable[None]]
TaskHandler = Callable[[ScheduledTask], Awaitable[None]]


async def start_ipc_watcher(
    group_folders: list[str],
    on_message: Optional[MessageHandler] = None,
    on_task: Optional[TaskHandler] = None,
    poll_interval: float = IPC_POLL_INTERVAL,
) -> None:
    """
    Poll IPC directories for incoming messages and tasks.

    This coroutine loops forever (until cancelled) and is meant to be
    started as an asyncio task.

    Args:
        group_folders: List of group folder names to watch.
        on_message: Async callback invoked for each new message file.
        on_task: Async callback invoked for each new task file.
        poll_interval: Seconds between polls.
    """
    log.info("IPC watcher started", groups=group_folders)

    async def _handle_message_file(path: Path) -> None:
        if on_message is None:
            return
        data = json.loads(path.read_text(encoding="utf-8"))
        msg = NewMessage(
            id=data.get("id", path.stem),
            chat_jid=data.get("chat_jid", ""),
            sender=data.get("sender", ""),
            sender_name=data.get("sender_name", ""),
            content=data.get("content", ""),
            timestamp=data.get("timestamp", ""),
            is_from_me=data.get("is_from_me", False),
            is_bot_message=data.get("is_bot_message", False),
        )
        await on_message(msg)

    async def _handle_task_file(path: Path) -> None:
        if on_task is None:
            return
        data = json.loads(path.read_text(encoding="utf-8"))
        task = ScheduledTask(
            id=data.get("id", path.stem),
            group_folder=data.get("group_folder", ""),
            chat_jid=data.get("chat_jid", ""),
            prompt=data.get("prompt", ""),
            schedule_type=data.get("schedule_type", "once"),
            schedule_value=data.get("schedule_value", ""),
            context_mode=data.get("context_mode", "group"),
            next_run=data.get("next_run"),
            last_run=data.get("last_run"),
            last_result=data.get("last_result"),
            status=data.get("status", "active"),
            created_at=data.get("created_at", ""),
        )
        await on_task(task)

    while True:
        for folder in group_folders:
            if on_message:
                await _poll_directory(_messages_dir(folder), _handle_message_file)
            if on_task:
                await _poll_directory(_tasks_dir(folder), _handle_task_file)

        await asyncio.sleep(poll_interval)
