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
from time import monotonic

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
from secnano.db import (
    get_chat,
    get_messages,
    get_registered_group,
    get_registered_group_by_jid,
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
from secnano.group_folder import is_valid_group_folder
from secnano.group_queue import GroupQueue
from secnano.ipc import start_ipc_watcher
from secnano.logger import configure_logging, get_logger, get_recent_events
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
_recent_agent_runs: deque[dict[str, object]] = deque(maxlen=40)


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


def _get_agent_run(run_id: str | None) -> dict[str, object] | None:
    if not run_id:
        return None
    for item in reversed(_recent_agent_runs):
        if item.get("run_id") == run_id:
            return item
    return None


def _matches_filter_text(candidate: object, query: str) -> bool:
    if candidate is None:
        return False
    if isinstance(candidate, dict):
        return any(_matches_filter_text(value, query) for value in candidate.values())
    if isinstance(candidate, (list, tuple, set)):
        return any(_matches_filter_text(value, query) for value in candidate)
    return query in str(candidate).lower()


def _filter_items(items: list[dict[str, object]], query: str) -> list[dict[str, object]]:
    if not query:
        return items
    return [item for item in items if _matches_filter_text(item, query)]


def _build_trace_tokens(query: str, selected_run: dict[str, object] | None) -> set[str]:
    trace_tokens: set[str] = set()
    if selected_run is not None:
        for key in ("run_id", "trace_id", "jid", "group_folder"):
            value = selected_run.get(key)
            if value:
                trace_tokens.add(str(value).lower())
    if query:
        trace_tokens.add(query)
    return trace_tokens


def _is_due_iso(timestamp: object) -> bool:
    if not isinstance(timestamp, str) or not timestamp:
        return False
    try:
        scheduled_at = datetime.fromisoformat(timestamp.replace("Z", "+00:00"))
    except ValueError:
        return False
    if scheduled_at.tzinfo is None:
        scheduled_at = scheduled_at.replace(tzinfo=UTC)
    return datetime.now(UTC) >= scheduled_at


def _derive_ops_summary(
    *,
    channels: list[dict[str, object]],
    queues: list[dict[str, object]],
    scheduled_tasks: list[dict[str, object]],
    recent_events: list[dict[str, object]],
    agent_runs: list[dict[str, object]],
) -> dict[str, object]:
    connected_channels = sum(1 for item in channels if item.get("connected"))
    active_agents = sum(
        1
        for item in queues
        if item.get("pid") is not None and item.get("returncode") is None
    )
    queued_items = sum(int(item.get("queue_size") or 0) for item in queues)
    due_tasks = sum(1 for item in scheduled_tasks if _is_due_iso(item.get("next_run")))
    recent_errors = sum(1 for item in recent_events if item.get("level") == "error")
    recent_errors += sum(1 for item in agent_runs if item.get("status") == "error")

    health = "good"
    if connected_channels == 0 or recent_errors > 0:
        health = "bad"
    elif queued_items > 0 or active_agents > 0 or due_tasks > 0:
        health = "warn"

    alerts: list[str] = []
    if connected_channels == 0:
        alerts.append("No channels are connected.")
    if queued_items > 0:
        alerts.append(f"{queued_items} queued item(s) are waiting in group queues.")
    if active_agents > 0:
        alerts.append(f"{active_agents} agent run(s) are active right now.")
    if due_tasks > 0:
        alerts.append(f"{due_tasks} scheduled task(s) are already due.")
    if recent_errors > 0:
        alerts.append(f"{recent_errors} recent error signal(s) need attention.")
    if not alerts:
        alerts.append("System looks healthy from the latest flow signals.")

    highlights = [
        f"{connected_channels} connected channel(s)",
        f"{active_agents} active agent(s)",
        f"{queued_items} queued item(s)",
        f"{len(agent_runs)} recent agent run(s)",
    ]

    return {
        "health": health,
        "alerts": alerts[:4],
        "highlights": highlights,
        "metrics": {
            "connected_channels": connected_channels,
            "active_agents": active_agents,
            "queued_items": queued_items,
            "due_tasks": due_tasks,
            "recent_errors": recent_errors,
        },
    }


def _build_graph_snapshot(
    *,
    channels: list[dict[str, object]],
    registered_groups: list[dict[str, object]],
    queues: list[dict[str, object]],
    scheduled_tasks: list[dict[str, object]],
    sessions: list[dict[str, object]],
    recent_messages: list[dict[str, object]],
    recent_events: list[dict[str, object]],
    agent_runs: list[dict[str, object]],
    query: str,
    selected_run: dict[str, object] | None,
) -> dict[str, object]:
    trace_tokens = _build_trace_tokens(query, selected_run)

    def _matches_tokens(item: dict[str, object]) -> bool:
        if not trace_tokens:
            return True
        return any(_matches_filter_text(item, token) for token in trace_tokens)

    connected_channels = sum(1 for item in channels if item.get("connected"))
    active_agents = [
        item for item in queues if item.get("pid") is not None and item.get("returncode") is None
    ]
    queued_items = sum(int(item.get("queue_size") or 0) for item in queues)
    due_tasks = sum(1 for item in scheduled_tasks if _is_due_iso(item.get("next_run")))
    recent_error_events = [item for item in recent_events if item.get("level") == "error"]
    recent_error_runs = [item for item in agent_runs if item.get("status") == "error"]

    channel_labels = [str(item.get("jid")) for item in channels if item.get("jid")]
    active_agent_labels = [str(item.get("jid")) for item in active_agents if item.get("jid")]

    nodes = [
        {
            "id": "web_ui",
            "label": "Web UI",
            "x": 80,
            "y": 120,
            "width": 170,
            "height": 88,
            "status": "active" if any(item.get("jid") == DEFAULT_MAIN_JID for item in recent_messages) else "good",
            "metrics": [
                {"label": "main", "value": DEFAULT_MAIN_JID},
                {"label": "recent", "value": str(sum(1 for item in recent_messages if item.get("jid") == DEFAULT_MAIN_JID or item.get("chat_jid") == DEFAULT_MAIN_JID))},
            ],
            "detail": {
                "title": "Web UI",
                "summary": "Browser chat entry point for the local main conversation.",
                "items": [
                    {"label": "Default JID", "value": DEFAULT_MAIN_JID},
                    {"label": "Recent visible messages", "value": str(len(recent_messages))},
                ],
            },
        },
        {
            "id": "channels",
            "label": "Channels",
            "x": 300,
            "y": 120,
            "width": 180,
            "height": 96,
            "status": "bad" if connected_channels == 0 else ("active" if connected_channels else "good"),
            "metrics": [
                {"label": "connected", "value": f"{connected_channels}/{len(channels) or 1}"},
                {"label": "jids", "value": ", ".join(channel_labels[:2]) or "n/a"},
            ],
            "detail": {
                "title": "Channels",
                "summary": "Inbound and outbound channel adapters currently attached to the host.",
                "items": [
                    {"label": "Connected", "value": str(connected_channels)},
                    {"label": "Known channels", "value": ", ".join(str(item.get("name")) for item in channels) or "n/a"},
                ],
            },
        },
        {
            "id": "host_router",
            "label": "Host Router",
            "x": 540,
            "y": 120,
            "width": 190,
            "height": 96,
            "status": "active" if any((_event.get("fields") or {}).get("flow") in {"message", "ipc_task"} for _event in recent_events[:12]) else "good",
            "metrics": [
                {"label": "recent flows", "value": str(sum(1 for event in recent_events[:20] if (event.get("fields") or {}).get("flow") in {"message", "ipc_task"}))},
                {"label": "errors", "value": str(len(recent_error_events))},
            ],
            "detail": {
                "title": "Host Router",
                "summary": "Stores inbound data, checks routing, and hands work off to queues.",
                "items": [
                    {"label": "Recent events", "value": str(len(recent_events))},
                    {"label": "Error signals", "value": str(len(recent_error_events))},
                ],
            },
        },
        {
            "id": "messages_db",
            "label": "Messages DB",
            "x": 780,
            "y": 48,
            "width": 180,
            "height": 88,
            "status": "active" if recent_messages else "good",
            "metrics": [
                {"label": "recent rows", "value": str(len(recent_messages))},
                {"label": "latest", "value": str(recent_messages[0].get("timestamp")) if recent_messages else "n/a"},
            ],
            "detail": {
                "title": "Messages DB",
                "summary": "Persistent message log used for prompt assembly and audits.",
                "items": [
                    {"label": "Recent rows", "value": str(len(recent_messages))},
                    {"label": "Top chat", "value": str(recent_messages[0].get("chat_jid")) if recent_messages else "n/a"},
                ],
            },
        },
        {
            "id": "chat_metadata",
            "label": "Chat Metadata",
            "x": 780,
            "y": 176,
            "width": 180,
            "height": 88,
            "status": "active" if registered_groups else "good",
            "metrics": [
                {"label": "known chats", "value": str(len({item.get('chat_jid') for item in recent_messages if item.get('chat_jid')}))},
                {"label": "groups", "value": str(len(registered_groups))},
            ],
            "detail": {
                "title": "Chat Metadata",
                "summary": "Stores chat names, channels, and grouping information.",
                "items": [
                    {"label": "Registered groups", "value": str(len(registered_groups))},
                    {"label": "Main group", "value": next((str(item.get("jid")) for item in registered_groups if item.get("is_main")), "n/a")},
                ],
            },
        },
        {
            "id": "registered_groups",
            "label": "Registered Groups",
            "x": 540,
            "y": 302,
            "width": 190,
            "height": 96,
            "status": "bad" if not registered_groups else "active",
            "metrics": [
                {"label": "count", "value": str(len(registered_groups))},
                {"label": "main", "value": next((str(item.get("folder")) for item in registered_groups if item.get("is_main")), "n/a")},
            ],
            "detail": {
                "title": "Registered Groups",
                "summary": "Routing table that binds a chat JID to a working folder and trigger policy.",
                "items": [
                    {"label": "Count", "value": str(len(registered_groups))},
                    {"label": "Folders", "value": ", ".join(str(item.get("folder")) for item in registered_groups[:3]) or "n/a"},
                ],
            },
        },
        {
            "id": "group_queue",
            "label": "Group Queue",
            "x": 780,
            "y": 318,
            "width": 180,
            "height": 96,
            "status": "bad" if queued_items >= 4 else ("warn" if queued_items > 0 else ("active" if active_agents else "good")),
            "metrics": [
                {"label": "queued", "value": str(queued_items)},
                {"label": "running", "value": ", ".join(active_agent_labels[:2]) or "idle"},
            ],
            "detail": {
                "title": "Group Queue",
                "summary": "Per-JID serial executor. Work is queued here before an agent process runs.",
                "items": [
                    {"label": "Queued items", "value": str(queued_items)},
                    {"label": "Active agents", "value": str(len(active_agents))},
                ],
            },
        },
        {
            "id": "agent_runner",
            "label": "Agent Runner",
            "x": 1040,
            "y": 318,
            "width": 180,
            "height": 96,
            "status": "bad" if recent_error_runs else ("active" if active_agents else "good"),
            "metrics": [
                {"label": "running", "value": str(len(active_agents))},
                {"label": "recent runs", "value": str(len(agent_runs))},
            ],
            "detail": {
                "title": "Agent Runner",
                "summary": "Subprocess execution boundary for prompts, tool use, and replies.",
                "items": [
                    {"label": "Active agents", "value": str(len(active_agents))},
                    {"label": "Recent errors", "value": str(len(recent_error_runs))},
                ],
            },
        },
        {
            "id": "sessions",
            "label": "Sessions",
            "x": 1300,
            "y": 228,
            "width": 160,
            "height": 84,
            "status": "active" if sessions else "good",
            "metrics": [
                {"label": "tracked", "value": str(len(sessions))},
                {"label": "latest", "value": str(sessions[0].get("group_folder")) if sessions else "n/a"},
            ],
            "detail": {
                "title": "Sessions",
                "summary": "Conversation continuity stored per working folder.",
                "items": [
                    {"label": "Tracked sessions", "value": str(len(sessions))},
                    {"label": "Latest folder", "value": str(sessions[0].get("group_folder")) if sessions else "n/a"},
                ],
            },
        },
        {
            "id": "scheduled_tasks",
            "label": "Scheduled Tasks",
            "x": 1040,
            "y": 486,
            "width": 190,
            "height": 92,
            "status": "bad" if due_tasks > 0 else ("active" if scheduled_tasks else "good"),
            "metrics": [
                {"label": "count", "value": str(len(scheduled_tasks))},
                {"label": "due", "value": str(due_tasks)},
            ],
            "detail": {
                "title": "Scheduled Tasks",
                "summary": "Tasks that enqueue work into a group queue on a time-based schedule.",
                "items": [
                    {"label": "Configured tasks", "value": str(len(scheduled_tasks))},
                    {"label": "Already due", "value": str(due_tasks)},
                ],
            },
        },
    ]

    edges = [
        {
            "id": "web_to_channels",
            "source": "web_ui",
            "target": "channels",
            "label": "User input",
            "status": "active",
            "detail": {
                "title": "Web UI -> Channels",
                "summary": "Messages entering the system from the browser surface.",
            },
        },
        {
            "id": "channels_to_host",
            "source": "channels",
            "target": "host_router",
            "label": "Inbound",
            "status": "active" if recent_messages else "good",
            "detail": {
                "title": "Channels -> Host Router",
                "summary": "Raw incoming messages and metadata reaching the host orchestrator.",
            },
        },
        {
            "id": "host_to_messages",
            "source": "host_router",
            "target": "messages_db",
            "label": "Store message",
            "status": "active" if recent_messages else "good",
            "detail": {
                "title": "Host Router -> Messages DB",
                "summary": "Incoming messages are persisted before routing decisions are made.",
            },
        },
        {
            "id": "host_to_metadata",
            "source": "host_router",
            "target": "chat_metadata",
            "label": "Update chat",
            "status": "good",
            "detail": {
                "title": "Host Router -> Chat Metadata",
                "summary": "Chat names and channel metadata updates are stored here.",
            },
        },
        {
            "id": "host_to_groups",
            "source": "host_router",
            "target": "registered_groups",
            "label": "Route lookup",
            "status": "warn" if any((event.get("fields") or {}).get("stage") in {"no_registered_group", "trigger_miss"} for event in recent_events[:20]) else "good",
            "detail": {
                "title": "Host Router -> Registered Groups",
                "summary": "Message JIDs are matched to group registrations and trigger policies.",
            },
        },
        {
            "id": "host_to_queue",
            "source": "host_router",
            "target": "group_queue",
            "label": "Enqueue",
            "status": "bad" if queued_items >= 4 else ("warn" if queued_items > 0 else "good"),
            "detail": {
                "title": "Host Router -> Group Queue",
                "summary": "Accepted messages are enqueued here for serial execution.",
            },
        },
        {
            "id": "tasks_to_queue",
            "source": "scheduled_tasks",
            "target": "group_queue",
            "label": "Scheduled enqueue",
            "status": "bad" if due_tasks > 0 else ("active" if scheduled_tasks else "good"),
            "detail": {
                "title": "Scheduled Tasks -> Group Queue",
                "summary": "Timer-driven work enters the same per-group queue pipeline here.",
            },
        },
        {
            "id": "queue_to_agent",
            "source": "group_queue",
            "target": "agent_runner",
            "label": "Run agent",
            "status": "bad" if recent_error_runs else ("active" if active_agents else "good"),
            "detail": {
                "title": "Group Queue -> Agent Runner",
                "summary": "Prompt execution starts here once a group becomes runnable.",
            },
        },
        {
            "id": "agent_to_sessions",
            "source": "agent_runner",
            "target": "sessions",
            "label": "Session update",
            "status": "active" if sessions else "good",
            "detail": {
                "title": "Agent Runner -> Sessions",
                "summary": "Session continuity is refreshed when agent runs return new session IDs.",
            },
        },
        {
            "id": "agent_to_channels",
            "source": "agent_runner",
            "target": "channels",
            "label": "Reply",
            "status": "active" if any((event.get("fields") or {}).get("stage") == "reply_sent" for event in recent_events[:20]) else "good",
            "detail": {
                "title": "Agent Runner -> Channels",
                "summary": "Final replies are emitted back through the owning channel.",
            },
        },
    ]

    packets: list[dict[str, object]] = []

    def _add_packet(
        *,
        edge_id: str,
        kind: str,
        label: str,
        preview: str | None,
        timestamp: str | None,
        status: str = "active",
        trace_id: str | None = None,
        run_id: str | None = None,
        slot: int = 0,
    ) -> None:
        packet = {
            "id": f"{edge_id}:{trace_id or run_id or timestamp or len(packets)}:{slot}",
            "edge_id": edge_id,
            "kind": kind,
            "label": label,
            "preview": _truncate(preview, 80) if preview else None,
            "timestamp": timestamp,
            "status": status,
            "trace_id": trace_id,
            "run_id": run_id,
            "slot": slot,
        }
        if _matches_tokens(packet):
            packets.append(packet)

    for index, message in enumerate(recent_messages[:10]):
        if message.get("is_from_me") or message.get("is_bot_message"):
            continue
        _add_packet(
            edge_id="web_to_channels",
            kind="message",
            label=str(message.get("chat_jid") or "message"),
            preview=str(message.get("content") or ""),
            timestamp=str(message.get("timestamp") or ""),
            trace_id=str(message.get("id") or ""),
            slot=index,
        )

    for index, event in enumerate(recent_events[:40]):
        fields = event.get("fields") or {}
        if not isinstance(fields, dict):
            continue
        flow = str(fields.get("flow") or "")
        stage = str(fields.get("stage") or "")
        edge_id: str | None = None
        kind = "event"
        label = str(fields.get("jid") or fields.get("task_id") or event.get("event") or "event")
        preview = str(event.get("event") or "")
        status = "bad" if event.get("level") == "error" else "active"
        run_id = str(fields.get("run_id") or fields.get("task_id") or "")
        trace_id = str(fields.get("trace_id") or "")

        if flow == "message" and stage == "received":
            edge_id = "channels_to_host"
            kind = "message"
        elif flow == "message" and stage == "stored":
            edge_id = "host_to_messages"
            kind = "message"
        elif flow == "message" and stage in {"queued"}:
            edge_id = "host_to_queue"
            kind = "queue"
        elif flow == "message" and stage in {"trigger_miss", "no_registered_group"}:
            edge_id = "host_to_groups"
            kind = "routing"
            status = "warn"
        elif flow == "agent_run" and stage in {"start", "prompt_prepared", "subprocess_started"}:
            edge_id = "queue_to_agent"
            kind = "agent"
        elif flow == "agent_run" and stage in {"output_received", "completed"}:
            edge_id = "agent_to_sessions"
            kind = "session"
        elif flow == "agent_run" and stage in {"reply_sent", "reply_skipped_no_channel"}:
            edge_id = "agent_to_channels"
            kind = "reply"
            status = "warn" if stage == "reply_skipped_no_channel" else "active"
        elif flow == "scheduled_task" and stage == "start":
            edge_id = "tasks_to_queue"
            kind = "task"
        elif flow == "scheduled_task" and stage == "reply_sent":
            edge_id = "agent_to_channels"
            kind = "reply"

        if edge_id is None:
            continue

        _add_packet(
            edge_id=edge_id,
            kind=kind,
            label=label,
            preview=preview,
            timestamp=str(event.get("timestamp") or ""),
            status=status,
            trace_id=trace_id or None,
            run_id=run_id or None,
            slot=index,
        )

    for index, run in enumerate(agent_runs[:10]):
        if run.get("status") != "success":
            continue
        _add_packet(
            edge_id="agent_to_channels",
            kind="reply",
            label=str(run.get("jid") or "reply"),
            preview=str(run.get("reply_preview") or ""),
            timestamp=str(run.get("completed_at") or run.get("started_at") or ""),
            status="active",
            trace_id=str(run.get("trace_id") or ""),
            run_id=str(run.get("run_id") or ""),
            slot=50 + index,
        )

    packets = packets[:24]

    edge_packet_counts: dict[str, int] = {}
    for packet in packets:
        edge_id = str(packet.get("edge_id"))
        edge_packet_counts[edge_id] = edge_packet_counts.get(edge_id, 0) + 1

    for edge in edges:
        edge["packet_count"] = edge_packet_counts.get(str(edge["id"]), 0)

    return {"nodes": nodes, "edges": edges, "packets": packets}


def _build_timeline(
    *,
    query: str,
    selected_run: dict[str, object] | None,
    recent_events: list[dict[str, object]],
    recent_messages: list[dict[str, object]],
    task_runs: list[dict[str, object]],
    agent_runs: list[dict[str, object]],
) -> list[dict[str, object]]:
    timeline: list[dict[str, object]] = []
    trace_tokens = _build_trace_tokens(query, selected_run)

    if selected_run is not None:
        timeline.append(
            {
                "kind": "agent_run",
                "timestamp": selected_run.get("started_at"),
                "title": f"Agent run {selected_run.get('run_id')}",
                "summary": selected_run.get("reply_preview") or selected_run.get("status"),
                "fields": selected_run,
            }
        )

    def _matches_tokens(item: dict[str, object]) -> bool:
        if not trace_tokens:
            return True
        return any(_matches_filter_text(item, token) for token in trace_tokens)

    for event in recent_events:
        if _matches_tokens(event):
            timeline.append(
                {
                    "kind": "event",
                    "timestamp": event.get("timestamp"),
                    "title": event.get("event"),
                    "summary": event.get("logger"),
                    "fields": event,
                }
            )

    for message in recent_messages:
        if _matches_tokens(message):
            timeline.append(
                {
                    "kind": "message",
                    "timestamp": message.get("timestamp"),
                    "title": str(message.get("sender") or "message"),
                    "summary": _truncate(str(message.get("content") or ""), 160),
                    "fields": message,
                }
            )

    for task_run in task_runs:
        if _matches_tokens(task_run):
            timeline.append(
                {
                    "kind": "task_run",
                    "timestamp": task_run.get("run_at"),
                    "title": str(task_run.get("task_id") or "task"),
                    "summary": task_run.get("status"),
                    "fields": task_run,
                }
            )

    for run in agent_runs:
        if selected_run is not None and run.get("run_id") == selected_run.get("run_id"):
            continue
        if _matches_tokens(run):
            timeline.append(
                {
                    "kind": "agent_run",
                    "timestamp": run.get("started_at"),
                    "title": str(run.get("run_id") or "agent-run"),
                    "summary": run.get("status"),
                    "fields": run,
                }
            )

    timeline.sort(key=lambda item: str(item.get("timestamp") or ""), reverse=True)
    return timeline[:80]


def _build_ops_snapshot(
    filter_text: str | None = None,
    selected_run_id: str | None = None,
) -> dict[str, object]:
    query = (filter_text or "").strip().lower()
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
    recent_events = get_recent_events(limit=80)
    agent_runs = list(_recent_agent_runs)
    selected_run = _get_agent_run(selected_run_id)
    visible_agent_runs = _filter_items(agent_runs, query)
    timeline = _build_timeline(
        query=query,
        selected_run=selected_run,
        recent_events=recent_events,
        recent_messages=recent_messages,
        task_runs=task_runs,
        agent_runs=agent_runs,
    )
    summary = _derive_ops_summary(
        channels=channels,
        queues=queues,
        scheduled_tasks=scheduled_tasks,
        recent_events=recent_events,
        agent_runs=agent_runs,
    )
    graph = _build_graph_snapshot(
        channels=channels,
        registered_groups=registered_groups,
        queues=queues,
        scheduled_tasks=scheduled_tasks,
        sessions=sessions,
        recent_messages=recent_messages,
        recent_events=recent_events,
        agent_runs=agent_runs,
        query=query,
        selected_run=selected_run,
    )

    return {
        "filter": filter_text or "",
        "selected_run_id": selected_run_id or "",
        "summary": summary,
        "graph": graph,
        "channels": _filter_items(channels, query),
        "registered_groups": _filter_items(registered_groups, query),
        "queues": _filter_items(queues, query),
        "scheduled_tasks": _filter_items(scheduled_tasks, query),
        "task_runs": _filter_items(task_runs, query),
        "sessions": _filter_items(sessions, query),
        "recent_messages": _filter_items(recent_messages, query),
        "chats": _filter_items(chats, query),
        "recent_events": _filter_items(recent_events, query),
        "agent_runs": visible_agent_runs,
        "selected_agent_run": selected_run,
        "trace_timeline": timeline,
    }


async def _process_group_messages(
    group: RegisteredGroup,
    messages: list[Message],
    trace_id: str | None = None,
) -> None:
    """Invoke the agent subprocess for a group and handle its output."""
    chat_jid = group.jid
    channel = find_channel(_channels, chat_jid)
    run_id = str(uuid.uuid4())
    effective_trace_id = trace_id or run_id
    typing_cleared = False
    close_requested = False
    started_at = _now_utc()
    started_monotonic = monotonic()
    prompt_preview: str | None = None

    log.info(
        "Agent run starting",
        flow="agent_run",
        stage="start",
        run_id=run_id,
        trace_id=effective_trace_id,
        jid=chat_jid,
        folder=group.folder,
        has_channel=channel is not None,
    )

    # Build the conversation prompt from recent DB messages
    recent = get_messages(chat_jid, limit=50)
    prompt = format_messages(recent, "UTC")
    prompt_preview = _truncate(prompt)
    log.info(
        "Agent prompt prepared",
        flow="agent_run",
        stage="prompt_prepared",
        run_id=run_id,
        trace_id=effective_trace_id,
        jid=chat_jid,
        message_count=len(recent),
    )

    if not prompt.strip():
        log.info(
            "Skipping empty prompt",
            flow="agent_run",
            stage="empty_prompt",
            run_id=run_id,
            trace_id=effective_trace_id,
            jid=chat_jid,
        )
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
        nonlocal typing_cleared, close_requested
        log.info(
            "Agent output received",
            flow="agent_run",
            stage="output_received",
            run_id=run_id,
            trace_id=effective_trace_id,
            jid=chat_jid,
            has_result=output.result is not None,
            status=output.status,
        )
        if output.result:
            text = format_outbound(output.result)
            if text and channel:
                try:
                    await channel.send_message(chat_jid, text)
                    _store_bot_message(chat_jid, text, group.folder)
                    log.info(
                        "Agent reply sent",
                        flow="agent_run",
                        stage="reply_sent",
                        run_id=run_id,
                        trace_id=effective_trace_id,
                        jid=chat_jid,
                        chars=len(text),
                    )
                except Exception as exc:
                    log.error("Failed to send message", error=str(exc))
            elif text:
                log.info(
                    "Agent reply produced without channel",
                    flow="agent_run",
                    stage="reply_skipped_no_channel",
                    run_id=run_id,
                    trace_id=effective_trace_id,
                    jid=chat_jid,
                    chars=len(text),
                )

        if output.new_session_id:
            _save_session(group.folder, output.new_session_id)

        if channel and not typing_cleared and (output.result is not None or output.status == "error"):
            import contextlib
            with contextlib.suppress(Exception):
                await channel.set_typing(chat_jid, False)
            typing_cleared = True

        if not close_requested:
            import contextlib
            with contextlib.suppress(Exception):
                await _group_queue.close_stdin(chat_jid)
            close_requested = True

    def _on_process(proc: asyncio.subprocess.Process, name: str, folder: str) -> None:
        _group_queue.register_process(chat_jid, proc, name, folder)
        log.info(
            "Agent subprocess registered",
            flow="agent_run",
            stage="subprocess_started",
            run_id=run_id,
            trace_id=effective_trace_id,
            jid=chat_jid,
            folder=folder,
            pid=proc.pid,
            subprocess_name=name,
        )

    try:
        result = await run_subprocess_agent(
            group=group,
            input_data=input_data,
            on_process=_on_process,
            on_output=_on_output,
        )

        if result.status == "error":
            log.error("Agent subprocess error", group=group.folder, error=result.error)
        else:
            log.info(
                "Agent run completed",
                flow="agent_run",
                stage="completed",
                run_id=run_id,
                trace_id=effective_trace_id,
                jid=chat_jid,
                had_result=result.result is not None,
            )
        _record_agent_run(
            {
                "run_id": run_id,
                "trace_id": effective_trace_id,
                "kind": "message",
                "jid": chat_jid,
                "group_folder": group.folder,
                "started_at": started_at,
                "completed_at": _now_utc(),
                "duration_ms": int((monotonic() - started_monotonic) * 1000),
                "status": result.status,
                "prompt_preview": prompt_preview,
                "reply_preview": _truncate(format_outbound(result.result) if result.result else None),
                "prompt_full": prompt,
                "reply_full": format_outbound(result.result) if result.result else None,
                "error": result.error,
            }
        )
    finally:
        if channel and not typing_cleared:
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
    log.info(
        "IPC task received",
        flow="ipc_task",
        stage="received",
        task_id=task.id,
        source_group=task.source_group,
        type=task.type,
    )
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
    trigger = str(data.get("trigger", "")).strip()

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
        jid=jid,
        name=name,
        folder=folder,
        trigger=trigger,
        added_at=_now_utc(),
        requires_trigger=requires_trigger,
        is_main=False,
    )
    upsert_registered_group(group)

    # Ensure workspace and IPC directories exist for the newly registered group.
    _ensure_group_dirs(folder)

    log.info(
        "Group registered via IPC task",
        flow="ipc_task",
        stage="completed",
        source_group=task.source_group,
        jid=jid,
        folder=folder,
        trigger=trigger,
    )


async def _handle_new_message(new_msg: NewMessage) -> None:
    """Process a new incoming message from any channel."""
    trace_id = new_msg.id or str(uuid.uuid4())
    log.info(
        "Inbound message received",
        flow="message",
        stage="received",
        trace_id=trace_id,
        jid=new_msg.chat_jid,
        sender=new_msg.sender,
    )
    if new_msg.is_bot_message or new_msg.is_from_me:
        log.info(
            "Inbound message skipped",
            flow="message",
            stage="skip_bot_or_self",
            trace_id=trace_id,
            jid=new_msg.chat_jid,
        )
        return

    if not is_sender_allowed(new_msg.sender):
        log.debug("Sender not in allowlist", sender=new_msg.sender)
        log.info(
            "Inbound message rejected by allowlist",
            flow="message",
            stage="allowlist_rejected",
            trace_id=trace_id,
            jid=new_msg.chat_jid,
            sender=new_msg.sender,
        )
        return

    # Persist chat metadata and message
    existing_chat = get_chat(new_msg.chat_jid)
    store_chat_metadata(
        chat_jid=new_msg.chat_jid,
        timestamp=new_msg.timestamp or _now_utc(),
        name=(existing_chat.name if existing_chat else None) or new_msg.sender_name or new_msg.chat_jid,
        channel=existing_chat.channel if existing_chat else "unknown",
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
    log.info(
        "Inbound message stored",
        flow="message",
        stage="stored",
        trace_id=trace_id,
        jid=new_msg.chat_jid,
    )

    # Find matching registered group
    matched = get_registered_group_by_jid(new_msg.chat_jid)
    if matched is None:
        log.info(
            "Inbound message stored without registered group",
            flow="message",
            stage="no_registered_group",
            trace_id=trace_id,
            jid=new_msg.chat_jid,
        )
        return

    # Check trigger requirement
    if not _matches_group_trigger(matched, new_msg.content):
        log.info(
            "Inbound message did not match trigger",
            flow="message",
            stage="trigger_miss",
            trace_id=trace_id,
            jid=new_msg.chat_jid,
            group_folder=matched.folder,
        )
        return

    log.info(
        "Queuing message for group",
        flow="message",
        stage="queued",
        trace_id=trace_id,
        group=matched.folder,
        jid=matched.jid,
        sender=new_msg.sender,
    )

    async def _run() -> None:
        await _process_group_messages(matched, [], trace_id=trace_id)

    await _group_queue.enqueue_task(new_msg.chat_jid, str(uuid.uuid4()), _run)


async def _handle_scheduled_task(task: ScheduledTask) -> str | None:
    """Run a scheduled task through the agent subprocess."""
    typing_cleared = False
    close_requested = False
    started_at = _now_utc()
    started_monotonic = monotonic()
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
    log.info(
        "Scheduled task execution starting",
        flow="scheduled_task",
        stage="start",
        task_id=task.id,
        trace_id=task.id,
        jid=task.chat_jid,
        group_folder=task.group_folder,
    )

    async def _on_output(output: SubprocessOutput) -> None:
        nonlocal typing_cleared, close_requested
        if output.result and channel:
            text = format_outbound(output.result)
            if text:
                try:
                    await channel.send_message(task.chat_jid, text)
                    _store_bot_message(task.chat_jid, text, task.group_folder)
                    log.info(
                        "Scheduled task reply sent",
                        flow="scheduled_task",
                        stage="reply_sent",
                        task_id=task.id,
                        trace_id=task.id,
                        jid=task.chat_jid,
                    )
                except Exception as exc:
                    log.error("Failed to send scheduled task result", error=str(exc))
        if output.new_session_id and task.context_mode == "group":
            _save_session(task.group_folder, output.new_session_id)
        if channel and not typing_cleared and (output.result is not None or output.status == "error"):
            import contextlib
            with contextlib.suppress(Exception):
                await channel.set_typing(task.chat_jid, False)
            typing_cleared = True
        if not close_requested:
            import contextlib
            with contextlib.suppress(Exception):
                await _group_queue.close_stdin(task.chat_jid)
            close_requested = True

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
        _record_agent_run(
            {
                "run_id": task.id,
                "trace_id": task.id,
                "kind": "scheduled_task",
                "jid": task.chat_jid,
                "group_folder": task.group_folder,
                "started_at": started_at,
                "completed_at": _now_utc(),
                "duration_ms": int((monotonic() - started_monotonic) * 1000),
                "status": result.status,
                "prompt_preview": _truncate(task.prompt),
                "reply_preview": None,
                "prompt_full": task.prompt,
                "reply_full": None,
                "error": result.error,
            }
        )
        raise RuntimeError(result.error or "Scheduled task subprocess failed")

    log.info(
        "Scheduled task execution completed",
        flow="scheduled_task",
        stage="completed",
        task_id=task.id,
        trace_id=task.id,
        jid=task.chat_jid,
    )
    _record_agent_run(
        {
            "run_id": task.id,
            "trace_id": task.id,
            "kind": "scheduled_task",
            "jid": task.chat_jid,
            "group_folder": task.group_folder,
            "started_at": started_at,
            "completed_at": _now_utc(),
            "duration_ms": int((monotonic() - started_monotonic) * 1000),
            "status": result.status,
            "prompt_preview": _truncate(task.prompt),
            "reply_preview": _truncate(format_outbound(result.result) if result.result else None),
            "prompt_full": task.prompt,
            "reply_full": format_outbound(result.result) if result.result else None,
            "error": result.error,
        }
    )

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
