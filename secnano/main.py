"""
Main orchestrator for secnano.

Coordinates channels, group queues, scheduled tasks, and IPC watchers.
"""

from __future__ import annotations

import asyncio
import re
import uuid
from collections import deque
from collections.abc import Awaitable, Callable
from datetime import UTC, datetime

from secnano.channels.registry import list_channels, register_channel
from secnano.channels.web import LocalWebChannel
from secnano.config import (
    ASSISTANT_NAME,
    DATA_DIR,
    DEFAULT_MAIN_FOLDER,
    DEFAULT_MAIN_JID,
    DEFAULT_MAIN_NAME,
    GROUPS_DIR,
    POLL_INTERVAL,
    TRIGGER_PATTERN,
    WEB_CHANNEL_HOST,
    WEB_CHANNEL_PORT,
)
from secnano.control_plane import handle_ipc_task as control_plane_handle_ipc_task
from secnano.db import (
    get_messages,
    get_registered_group,
    get_session,
    init_database,
    insert_message,
    list_chats,
    list_recent_messages,
    list_recent_task_run_logs,
    list_registered_groups,
    list_scheduled_tasks,
    list_sessions,
    store_chat_metadata,
    upsert_registered_group,
    upsert_session,
)
from secnano.group_queue import GroupQueue
from secnano.ingress import (
    handle_chat_metadata as ingress_handle_chat_metadata,
)
from secnano.ingress import (
    handle_new_message as ingress_handle_new_message,
)
from secnano.ipc import start_ipc_watcher
from secnano.logger import configure_logging, get_logger, get_recent_events
from secnano.ops_view import build_ops_snapshot as build_ops_debug_snapshot
from secnano.router import find_channel, format_messages, format_outbound
from secnano.runtime import SubprocessRuntimeAdapter
from secnano.runtime_orchestration import RuntimeOrchestrator
from secnano.sender_allowlist import is_sender_allowed
from secnano.subprocess_runner import run_subprocess_agent
from secnano.task_scheduler import start_scheduler_loop
from secnano.trace import get_trace_store
from secnano.types import (
    ChatMetadata,
    IpcTaskRequest,
    Message,
    NewMessage,
    RegisteredGroup,
    ScheduledTask,
    Session,
    TraceEvent,
)

log = get_logger("main")

_group_queue = GroupQueue()
_channels: list = []
_recent_agent_runs: deque[dict[str, object]] = deque(maxlen=40)
_trace_store = get_trace_store()
_runtime_adapter: SubprocessRuntimeAdapter | None = None
_runtime_orchestrator: RuntimeOrchestrator | None = None


def _now_utc() -> str:
    return datetime.now(UTC).isoformat()


def _get_runtime_adapter() -> SubprocessRuntimeAdapter:
    global _runtime_adapter
    if _runtime_adapter is None:
        _runtime_adapter = SubprocessRuntimeAdapter(run_agent=run_subprocess_agent)
    return _runtime_adapter


def _get_runtime_orchestrator() -> RuntimeOrchestrator:
    global _runtime_orchestrator
    if _runtime_orchestrator is None:
        _runtime_orchestrator = RuntimeOrchestrator(
            runtime_adapter=_get_runtime_adapter(),
            group_queue=_group_queue,
            channels=_channels,
            now_utc=_now_utc,
            get_session_id=_get_session_id,
            save_session=_save_session,
            store_bot_message=_store_bot_message,
            record_agent_run=_record_agent_run,
            list_registered_groups=list_registered_groups,
            format_outbound=format_outbound,
            truncate=_truncate,
            log=log,
            find_channel=find_channel,
            get_messages=get_messages,
            format_messages=format_messages,
            emit_trace=_emit_trace,
        )
    return _runtime_orchestrator


def _emit_trace(
    *,
    trace_id: str,
    category: str,
    stage: str,
    status: str,
    jid: str | None = None,
    group_folder: str | None = None,
    task_id: str | None = None,
    run_id: str | None = None,
    source: str | None = None,
    details: dict[str, object] | None = None,
) -> None:
    _trace_store.record(
        TraceEvent(
            event_id=str(uuid.uuid4()),
            trace_id=trace_id,
            timestamp=_now_utc(),
            category=category,
            stage=stage,
            status=status,
            jid=jid,
            group_folder=group_folder,
            task_id=task_id,
            run_id=run_id,
            source=source,
            details=details or {},
        )
    )


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


def _ensure_group_dirs(folder: str) -> None:
    (GROUPS_DIR / folder).mkdir(parents=True, exist_ok=True)
    group_ipc = DATA_DIR / "ipc" / folder
    for sub in ("input", "messages", "tasks", "chat_metadata"):
        (group_ipc / sub).mkdir(parents=True, exist_ok=True)


def _is_legacy_jid_trigger(trigger: str, jid: str) -> bool:
    normalized = trigger.strip()
    if not normalized:
        return True
    if normalized == jid:
        return True
    if ":" in normalized:
        return True
    return "@" in normalized and not normalized.startswith("@")


def _matches_group_trigger(group: RegisteredGroup, content: str) -> bool:
    requires_trigger = group.requires_trigger if group.requires_trigger is not None else True
    if not requires_trigger:
        return True

    normalized_content = content.strip()
    trigger = (group.trigger or "").strip()
    if not trigger or _is_legacy_jid_trigger(trigger, group.jid):
        return bool(TRIGGER_PATTERN.search(normalized_content))

    trigger_body = trigger[1:] if trigger.startswith("@") else trigger
    pattern = re.compile(rf"(?i)^@?{re.escape(trigger_body)}\b")
    return bool(pattern.search(normalized_content))


def _ensure_main_bootstrap() -> RegisteredGroup:
    existing_main = next((group for group in list_registered_groups() if group.is_main), None)
    if existing_main is not None:
        _ensure_group_dirs(existing_main.folder)
        return existing_main

    now = _now_utc()
    existing_folder = get_registered_group(DEFAULT_MAIN_FOLDER)
    group = (
        RegisteredGroup(
            jid=existing_folder.jid,
            name=existing_folder.name,
            folder=existing_folder.folder,
            trigger=existing_folder.trigger,
            added_at=existing_folder.added_at,
            subprocess_config=existing_folder.subprocess_config,
            requires_trigger=False,
            is_main=True,
        )
        if existing_folder is not None
        else RegisteredGroup(
            jid=DEFAULT_MAIN_JID,
            name=DEFAULT_MAIN_NAME,
            folder=DEFAULT_MAIN_FOLDER,
            trigger=f"@{ASSISTANT_NAME}",
            added_at=now,
            requires_trigger=False,
            is_main=True,
        )
    )
    upsert_registered_group(group)
    _ensure_group_dirs(group.folder)
    store_chat_metadata(
        chat_jid=group.jid,
        timestamp=now,
        name=group.name,
        channel="web" if group.jid.startswith("web:") else None,
        is_group=True,
    )
    log.info("Bootstrapped main group", jid=group.jid, folder=group.folder)
    return group


def _truncate(text: str | None, limit: int = 240) -> str | None:
    if text is None:
        return None
    compact = " ".join(text.split())
    if len(compact) <= limit:
        return compact
    return compact[: limit - 1] + "…"


def _record_agent_run(summary: dict[str, object]) -> None:
    _recent_agent_runs.append(summary)

def _build_ops_snapshot(
    filter_text: str | None = None,
    selected_run_id: str | None = None,
) -> dict[str, object]:
    channels = [
        {
            "name": channel.name,
            "connected": channel.is_connected(),
            "jid": getattr(channel, "chat_jid", None),
        }
        for channel in _channels
    ]
    registered_groups = [
        {
            "jid": group.jid,
            "name": group.name,
            "folder": group.folder,
            "trigger": group.trigger,
            "requires_trigger": group.requires_trigger,
            "is_main": group.is_main,
        }
        for group in list_registered_groups()
    ]
    queues = _group_queue.snapshot()
    scheduled_tasks = [
        {
            "id": task.id,
            "group_folder": task.group_folder,
            "chat_jid": task.chat_jid,
            "schedule_type": task.schedule_type,
            "schedule_value": task.schedule_value,
            "next_run": task.next_run,
            "last_run": task.last_run,
            "status": task.status,
        }
        for task in list_scheduled_tasks()
    ]
    task_runs = [
        {
            "task_id": log.task_id,
            "run_at": log.run_at,
            "duration_ms": log.duration_ms,
            "status": log.status,
            "error": log.error,
        }
        for log in list_recent_task_run_logs(limit=20)
    ]
    sessions = [
        {
            "group_folder": session.group_folder,
            "session_id": session.session_id,
            "updated_at": session.updated_at,
        }
        for session in list_sessions()
    ]
    recent_messages = [
        {
            "id": message.id,
            "chat_jid": message.chat_jid,
            "sender": message.sender_name or message.sender,
            "content": message.content,
            "timestamp": message.timestamp,
            "is_from_me": message.is_from_me,
            "is_bot_message": message.is_bot_message,
        }
        for message in list_recent_messages(limit=30)
    ]
    chats = [
        {
            "jid": chat.jid,
            "name": chat.name,
            "last_message_time": chat.last_message_time,
            "channel": chat.channel,
            "is_group": chat.is_group,
        }
        for chat in list_chats()[:20]
    ]
    # Ops timeline remains a debug/ops view built from recent logs and summaries.
    # CI and flow assertions should use the formal TraceEvent store instead.
    recent_events = get_recent_events(limit=80)
    agent_runs = list(_recent_agent_runs)
    return build_ops_debug_snapshot(
        filter_text=filter_text,
        selected_run_id=selected_run_id,
        channels=channels,
        registered_groups=registered_groups,
        queues=queues,
        scheduled_tasks=scheduled_tasks,
        task_runs=task_runs,
        sessions=sessions,
        recent_messages=recent_messages,
        chats=chats,
        recent_events=recent_events,
        agent_runs=agent_runs,
    )


async def _process_group_messages(
    group: RegisteredGroup,
    messages: list[Message],
    trace_id: str | None = None,
) -> None:
    await _get_runtime_orchestrator().process_group_messages(group, messages, trace_id=trace_id)


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
    await ingress_handle_chat_metadata(metadata, now_utc=_now_utc)


async def _handle_ipc_task(task: IpcTaskRequest) -> None:
    await control_plane_handle_ipc_task(
        task,
        log=log,
        now_utc=_now_utc,
        ensure_group_dirs=_ensure_group_dirs,
        emit_trace=_emit_trace,
    )


async def _handle_new_message(new_msg: NewMessage) -> None:
    await ingress_handle_new_message(
        new_msg,
        log=log,
        now_utc=_now_utc,
        emit_trace=_emit_trace,
        sender_allowed=is_sender_allowed,
        matches_group_trigger=_matches_group_trigger,
        process_group_messages=_process_group_messages,
        enqueue_task=_group_queue.enqueue_task,
    )


async def _handle_scheduled_task(task: ScheduledTask) -> str | None:
    return await _get_runtime_orchestrator().handle_scheduled_task(task)


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
    _ensure_main_bootstrap()
    register_channel(
        LocalWebChannel(
            on_message=_handle_new_message,
            on_chat_metadata=_handle_chat_metadata,
            host=WEB_CHANNEL_HOST,
            port=WEB_CHANNEL_PORT,
            chat_jid=DEFAULT_MAIN_JID,
            chat_name=DEFAULT_MAIN_NAME,
            history_loader=lambda: get_messages(DEFAULT_MAIN_JID, limit=100),
            ops_snapshot=_build_ops_snapshot,
        )
    )

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
            if isinstance(channel, LocalWebChannel):
                log.info("Web UI available", url=channel.url, jid=channel.chat_jid)
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
