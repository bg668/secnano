"""
Filesystem-based IPC watcher.

Polls ``data/ipc/{group}/messages/``, ``chat_metadata/``, and ``tasks/`` for
new JSON files written by external processes (e.g., channel bridges/agents).
"""

from __future__ import annotations

import asyncio
import json
from collections.abc import Awaitable, Callable
from pathlib import Path

from secnano.config import DATA_DIR, IPC_POLL_INTERVAL
from secnano.logger import get_logger
from secnano.types import ChatMetadata, IpcTaskRequest, NewMessage

log = get_logger("ipc")

_MESSAGES_DIR_NAME = "messages"
_TASKS_DIR_NAME = "tasks"
_CHAT_METADATA_DIR_NAME = "chat_metadata"


def _ipc_base(group_folder: str) -> Path:
    return DATA_DIR / "ipc" / group_folder


def _messages_dir(group_folder: str) -> Path:
    return _ipc_base(group_folder) / _MESSAGES_DIR_NAME


def _tasks_dir(group_folder: str) -> Path:
    return _ipc_base(group_folder) / _TASKS_DIR_NAME


def _chat_metadata_dir(group_folder: str) -> Path:
    return _ipc_base(group_folder) / _CHAT_METADATA_DIR_NAME


def _discover_group_folders(seed_groups: list[str] | None = None) -> list[str]:
    groups: set[str] = set(seed_groups or [])
    ipc_root = DATA_DIR / "ipc"
    if ipc_root.exists():
        for entry in ipc_root.iterdir():
            if entry.is_dir():
                groups.add(entry.name)
    return sorted(groups)


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
            import contextlib
            with contextlib.suppress(OSError):
                entry.unlink(missing_ok=True)


MessageHandler = Callable[[NewMessage], Awaitable[None]]
TaskHandler = Callable[[IpcTaskRequest], Awaitable[None]]
ChatMetadataHandler = Callable[[ChatMetadata], Awaitable[None]]


async def start_ipc_watcher(
    group_folders: list[str] | None = None,
    on_message: MessageHandler | None = None,
    on_task: TaskHandler | None = None,
    on_chat_metadata: ChatMetadataHandler | None = None,
    poll_interval: float = IPC_POLL_INTERVAL,
) -> None:
    """
    Poll IPC directories for incoming messages, chat metadata, and tasks.

    This coroutine loops forever (until cancelled) and is meant to be
    started as an asyncio task.

    Args:
        group_folders: Seed list of group folders; watcher also auto-discovers new IPC dirs.
        on_message: Async callback invoked for each new message file.
        on_task: Async callback invoked for each new task file.
        on_chat_metadata: Async callback invoked for each chat metadata file.
        poll_interval: Seconds between polls.
    """
    log.info("IPC watcher started", groups=group_folders or [])

    async def _handle_message_file(path: Path) -> None:
        data = json.loads(path.read_text(encoding="utf-8"))

        if data.get("type") == "chat_metadata":
            if on_chat_metadata is None:
                return
            metadata = ChatMetadata(
                chat_jid=data.get("chat_jid", ""),
                timestamp=data.get("timestamp", ""),
                name=data.get("name"),
                channel=data.get("channel"),
                is_group=data.get("is_group"),
            )
            await on_chat_metadata(metadata)
            return

        if on_message is None:
            return

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

    async def _handle_chat_metadata_file(path: Path) -> None:
        if on_chat_metadata is None:
            return
        data = json.loads(path.read_text(encoding="utf-8"))
        metadata = ChatMetadata(
            chat_jid=data.get("chat_jid", ""),
            timestamp=data.get("timestamp", ""),
            name=data.get("name"),
            channel=data.get("channel"),
            is_group=data.get("is_group"),
        )
        await on_chat_metadata(metadata)

    async def _handle_task_file(path: Path) -> None:
        if on_task is None:
            return
        data = json.loads(path.read_text(encoding="utf-8"))
        task_type = str(data.get("type") or "schedule_task")
        task = IpcTaskRequest(
            id=str(data.get("id") or path.stem),
            source_group=path.parent.parent.name,
            type=task_type,
            payload=data,
            timestamp=data.get("timestamp"),
        )
        await on_task(task)

    while True:
        folders = _discover_group_folders(group_folders)
        for folder in folders:
            if on_message:
                await _poll_directory(_messages_dir(folder), _handle_message_file)
            if on_task:
                await _poll_directory(_tasks_dir(folder), _handle_task_file)
            if on_chat_metadata:
                await _poll_directory(_chat_metadata_dir(folder), _handle_chat_metadata_file)

        await asyncio.sleep(poll_interval)
