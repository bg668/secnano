"""
Main orchestrator for secnano.

Coordinates channels, group queues, scheduled tasks, and IPC watchers.
"""

from __future__ import annotations

import asyncio
import uuid
from collections.abc import Awaitable, Callable
from datetime import UTC, datetime

from secnano.channels.registry import list_channels
from secnano.config import (
    ASSISTANT_NAME,
    DATA_DIR,
    GROUPS_DIR,
    POLL_INTERVAL,
    TRIGGER_PATTERN,
)
from secnano.db import (
    get_chat,
    get_messages,
    get_registered_group,
    get_session,
    init_database,
    insert_message,
    list_registered_groups,
    store_chat_metadata,
    upsert_registered_group,
    upsert_session,
)
from secnano.group_folder import is_valid_group_folder
from secnano.group_queue import GroupQueue
from secnano.ipc import start_ipc_watcher
from secnano.logger import configure_logging, get_logger
from secnano.router import find_channel, format_messages, format_outbound
from secnano.sender_allowlist import is_sender_allowed
from secnano.subprocess_runner import run_subprocess_agent
from secnano.task_scheduler import start_scheduler_loop
from secnano.types import (
    ChatMetadata,
    IpcTaskRequest,
    Message,
    NewMessage,
    RegisteredGroup,
    ScheduledTask,
    Session,
    SubprocessInput,
    SubprocessOutput,
)

log = get_logger("main")

_group_queue = GroupQueue()
_channels: list = []


def _now_utc() -> str:
    return datetime.now(UTC).isoformat()


def _get_session_id(group_folder: str) -> str | None:
    session = get_session(group_folder)
    return session.session_id if session else None


def _save_session(group_folder: str, session_id: str) -> None:
    sessions_dir = DATA_DIR / "sessions" / group_folder
    sessions_dir.mkdir(parents=True, exist_ok=True)
    history_path = str(sessions_dir / "history.json")
    session = Session(
        group_folder=group_folder,
        session_id=session_id,
        history_path=history_path,
        updated_at=_now_utc(),
    )
    upsert_session(session)


async def _process_group_messages(group: RegisteredGroup, messages: list[Message]) -> None:
    """Invoke the agent subprocess for a group and handle its output."""
    chat_jid = group.trigger
    channel = find_channel(_channels, chat_jid)

    # Build the conversation prompt from recent DB messages
    recent = get_messages(chat_jid, limit=50)
    prompt = format_messages(recent, "UTC")

    if not prompt.strip():
        return

    session_id = _get_session_id(group.folder)

    input_data = SubprocessInput(
        prompt=prompt,
        group_folder=group.folder,
        chat_jid=chat_jid,
        is_main=bool(group.is_main),
        session_id=session_id,
        assistant_name=ASSISTANT_NAME,
    )

    if channel:
        import contextlib
        with contextlib.suppress(Exception):
            await channel.set_typing(chat_jid, True)

    async def _on_output(output: SubprocessOutput) -> None:
        if output.result:
            text = format_outbound(output.result)
            if text and channel:
                try:
                    await channel.send_message(chat_jid, text)
                    _store_bot_message(chat_jid, text, group.folder)
                except Exception as exc:
                    log.error("Failed to send message", error=str(exc))

        if output.new_session_id:
            _save_session(group.folder, output.new_session_id)

    def _on_process(proc: asyncio.subprocess.Process, name: str, folder: str) -> None:
        _group_queue.register_process(chat_jid, proc, name, folder)

    try:
        result = await run_subprocess_agent(
            group=group,
            input_data=input_data,
            on_process=_on_process,
            on_output=_on_output,
        )

        if result.status == "error":
            log.error("Agent subprocess error", group=group.folder, error=result.error)
    finally:
        if channel:
            import contextlib
            with contextlib.suppress(Exception):
                await channel.set_typing(chat_jid, False)
        _group_queue.notify_idle(chat_jid)


def _store_bot_message(chat_jid: str, text: str, group_folder: str) -> None:
    msg = Message(
        id=str(uuid.uuid4()),
        chat_jid=chat_jid,
        sender="bot",
        sender_name=ASSISTANT_NAME,
        content=text,
        timestamp=_now_utc(),
        is_from_me=True,
        is_bot_message=True,
    )
    insert_message(msg)


async def _handle_chat_metadata(metadata: ChatMetadata) -> None:
    """Persist chat metadata without triggering message routing."""
    if not metadata.chat_jid:
        return

    store_chat_metadata(
        chat_jid=metadata.chat_jid,
        timestamp=metadata.timestamp or _now_utc(),
        name=metadata.name,
        channel=metadata.channel,
        is_group=metadata.is_group,
    )


async def _handle_ipc_task(task: IpcTaskRequest) -> None:
    """Process IPC task requests (currently: register_group)."""
    if task.type != "register_group":
        log.debug("Ignoring unsupported IPC task type", type=task.type, source_group=task.source_group)
        return

    source = get_registered_group(task.source_group)
    if source is None or not source.is_main:
        log.warning(
            "Unauthorized register_group attempt blocked",
            source_group=task.source_group,
            task_id=task.id,
        )
        return

    data = task.payload
    jid = str(data.get("jid", "")).strip()
    name = str(data.get("name", "")).strip()
    folder = str(data.get("folder", "")).strip()
    trigger = str(data.get("trigger", "")).strip() or jid

    if not (jid and name and folder and trigger):
        log.warning("Invalid register_group task payload", task_id=task.id, source_group=task.source_group)
        return
    if not is_valid_group_folder(folder):
        log.warning(
            "Invalid register_group folder name",
            task_id=task.id,
            source_group=task.source_group,
            folder=folder,
        )
        return

    existing = get_chat(jid)
    store_chat_metadata(
        chat_jid=jid,
        timestamp=task.timestamp or _now_utc(),
        name=name,
        channel=(data.get("channel") or (existing.channel if existing else None)),
        is_group=True,
    )

    requires_trigger_value = data.get("requires_trigger")
    requires_trigger: bool | None = None
    if isinstance(requires_trigger_value, bool):
        requires_trigger = requires_trigger_value
    elif isinstance(requires_trigger_value, str):
        lowered = requires_trigger_value.strip().lower()
        if lowered in {"true", "1", "yes"}:
            requires_trigger = True
        elif lowered in {"false", "0", "no"}:
            requires_trigger = False

    group = RegisteredGroup(
        name=name,
        folder=folder,
        trigger=trigger,
        added_at=_now_utc(),
        requires_trigger=requires_trigger,
        is_main=False,
    )
    upsert_registered_group(group)

    # Ensure workspace and IPC directories exist for the newly registered group.
    (GROUPS_DIR / folder).mkdir(parents=True, exist_ok=True)
    group_ipc = DATA_DIR / "ipc" / folder
    for sub in ("input", "messages", "tasks", "chat_metadata"):
        (group_ipc / sub).mkdir(parents=True, exist_ok=True)

    log.info(
        "Group registered via IPC task",
        source_group=task.source_group,
        folder=folder,
        trigger=trigger,
    )


async def _handle_new_message(new_msg: NewMessage) -> None:
    """Process a new incoming message from any channel."""
    if new_msg.is_bot_message or new_msg.is_from_me:
        return

    if not is_sender_allowed(new_msg.sender):
        log.debug("Sender not in allowlist", sender=new_msg.sender)
        return

    # Persist chat metadata and message
    store_chat_metadata(
        chat_jid=new_msg.chat_jid,
        timestamp=new_msg.timestamp or _now_utc(),
        name=new_msg.sender_name or new_msg.chat_jid,
        channel="unknown",
        is_group=True,
    )
    insert_message(
        Message(
            id=new_msg.id,
            chat_jid=new_msg.chat_jid,
            sender=new_msg.sender,
            sender_name=new_msg.sender_name,
            content=new_msg.content,
            timestamp=new_msg.timestamp or _now_utc(),
        )
    )

    # Find matching registered group
    groups = list_registered_groups()
    matched: RegisteredGroup | None = None
    for g in groups:
        if g.trigger == new_msg.chat_jid:
            matched = g
            break

    if matched is None:
        return

    # Check trigger requirement
    requires_trigger = matched.requires_trigger if matched.requires_trigger is not None else True
    if requires_trigger and not TRIGGER_PATTERN.search(new_msg.content):
        return

    log.info(
        "Queuing message for group",
        group=matched.folder,
        sender=new_msg.sender,
    )

    async def _run() -> None:
        await _process_group_messages(matched, [])

    await _group_queue.enqueue_task(new_msg.chat_jid, str(uuid.uuid4()), _run)


async def _handle_scheduled_task(task: ScheduledTask) -> str | None:
    """Run a scheduled task through the agent subprocess."""
    group = next(
        (g for g in list_registered_groups() if g.folder == task.group_folder),
        None,
    )
    if group is None:
        raise RuntimeError(f"Scheduled task references unknown group: {task.group_folder}")

    session_id = _get_session_id(task.group_folder) if task.context_mode == "group" else None

    input_data = SubprocessInput(
        prompt=task.prompt,
        group_folder=task.group_folder,
        chat_jid=task.chat_jid,
        is_main=bool(group.is_main),
        session_id=session_id,
        is_scheduled_task=True,
        assistant_name=ASSISTANT_NAME,
    )

    channel = find_channel(_channels, task.chat_jid)

    async def _on_output(output: SubprocessOutput) -> None:
        if output.result and channel:
            text = format_outbound(output.result)
            if text:
                try:
                    await channel.send_message(task.chat_jid, text)
                    _store_bot_message(task.chat_jid, text, task.group_folder)
                except Exception as exc:
                    log.error("Failed to send scheduled task result", error=str(exc))
        if output.new_session_id and task.context_mode == "group":
            _save_session(task.group_folder, output.new_session_id)

    def _on_process(proc: asyncio.subprocess.Process, name: str, folder: str) -> None:
        _group_queue.register_process(task.chat_jid, proc, name, folder)

    try:
        result = await run_subprocess_agent(
            group=group,
            input_data=input_data,
            on_process=_on_process,
            on_output=_on_output,
        )
    finally:
        _group_queue.notify_idle(task.chat_jid)

    if result.status == "error":
        raise RuntimeError(result.error or "Scheduled task subprocess failed")

    return result.result


def recover_pending_messages() -> None:
    """Re-enqueue any groups that had in-progress work at shutdown."""
    # For simplicity, iterate all registered groups and check for pending IPC messages
    groups = list_registered_groups()
    for group in groups:
        ipc_input = DATA_DIR / "ipc" / group.folder / "input"
        if ipc_input.exists() and any(ipc_input.iterdir()):
            log.info("Recovering pending IPC messages", group=group.folder)
            asyncio.create_task(_process_group_messages(group, []))


async def _enqueue_due_task(
    task: ScheduledTask,
    run: Callable[[], Awaitable[None]] | None = None,
) -> None:
    """
    Enqueue a due scheduled task into the per-group queue.

    The ``run`` callable is provided by ``task_scheduler``; it executes and
    updates run logs/next_run/status.
    """
    if run is None:
        return
    await _group_queue.enqueue_task(task.chat_jid, task.id, run)


async def main() -> None:
    configure_logging()
    log.info("secnano starting", assistant=ASSISTANT_NAME)

    # Ensure required directories exist
    for d in [DATA_DIR, GROUPS_DIR, DATA_DIR / "ipc", DATA_DIR / "sessions"]:
        d.mkdir(parents=True, exist_ok=True)

    init_database()

    # Discover group folders from registered groups
    groups = list_registered_groups()
    group_folders = [g.folder for g in groups]

    log.info("Registered groups", count=len(groups))

    # Start background tasks
    asyncio.create_task(
        start_scheduler_loop(
            runner=_handle_scheduled_task,
            enqueue=_enqueue_due_task,
        )
    )
    asyncio.create_task(
        start_ipc_watcher(
            group_folders=group_folders,
            on_message=_handle_new_message,
            on_task=_handle_ipc_task,
            on_chat_metadata=_handle_chat_metadata,
        )
    )

    recover_pending_messages()

    # Connect all registered channels
    channels = list_channels()
    _channels.extend(channels)
    for channel in channels:
        try:
            await channel.connect()
            log.info("Channel connected", name=channel.name)
        except Exception as exc:
            log.error("Failed to connect channel", name=channel.name, error=str(exc))

    log.info("secnano running. Press Ctrl+C to stop.")

    try:
        while True:
            await asyncio.sleep(POLL_INTERVAL)
    except (KeyboardInterrupt, asyncio.CancelledError):
        log.info("Shutting down...")
        await _group_queue.shutdown(grace_period_ms=5000)
        import contextlib
        for channel in _channels:
            with contextlib.suppress(Exception):
                await channel.disconnect()


def main_cli() -> None:
    """Entry point for the ``secnano`` CLI command."""
    import contextlib
    with contextlib.suppress(KeyboardInterrupt):
        asyncio.run(main())


if __name__ == "__main__":
    main_cli()
