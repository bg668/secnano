"""
Ops/debug snapshot builders.

This module intentionally serves the local ops/debug UI only.
It is not the formal TraceEvent source used for CI assertions.
"""

from __future__ import annotations

from datetime import UTC, datetime


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

    return {
        "health": health,
        "alerts": alerts[:4],
        "highlights": [
            f"{connected_channels} connected channel(s)",
            f"{active_agents} active agent(s)",
            f"{queued_items} queued item(s)",
            f"{len(agent_runs)} recent agent run(s)",
        ],
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
    queues: list[dict[str, object]],
    scheduled_tasks: list[dict[str, object]],
    recent_messages: list[dict[str, object]],
    recent_events: list[dict[str, object]],
    agent_runs: list[dict[str, object]],
) -> dict[str, object]:
    connected_channels = sum(1 for item in channels if item.get("connected"))
    active_agents = sum(
        1 for item in queues if item.get("pid") is not None and item.get("returncode") is None
    )
    due_tasks = sum(1 for item in scheduled_tasks if _is_due_iso(item.get("next_run")))

    nodes = [
        {"id": "channels", "label": "Channels", "value": connected_channels},
        {"id": "messages", "label": "Messages", "value": len(recent_messages)},
        {"id": "queues", "label": "Queues", "value": sum(int(item.get("queue_size") or 0) for item in queues)},
        {"id": "agents", "label": "Agent Runs", "value": active_agents},
        {"id": "tasks", "label": "Scheduled Tasks", "value": due_tasks},
    ]
    packets = [
        {
            "id": f"event:{index}",
            "kind": "event",
            "timestamp": event.get("timestamp"),
            "label": str((event.get("fields") or {}).get("stage") or event.get("event") or "event"),
        }
        for index, event in enumerate(recent_events[:12])
    ]
    edges = [
        {"id": "channels_to_queue", "source": "channels", "target": "queues"},
        {"id": "queue_to_agents", "source": "queues", "target": "agents"},
        {"id": "tasks_to_queue", "source": "tasks", "target": "queues"},
    ]
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

    def _matches_tokens(item: dict[str, object]) -> bool:
        if not trace_tokens:
            return True
        return any(_matches_filter_text(item, token) for token in trace_tokens)

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

    for collection_name, items in (
        ("event", recent_events),
        ("message", recent_messages),
        ("task_run", task_runs),
        ("agent_run", agent_runs),
    ):
        for item in items:
            if collection_name == "agent_run" and selected_run and item.get("run_id") == selected_run.get("run_id"):
                continue
            if not _matches_tokens(item):
                continue
            timeline.append(
                {
                    "kind": collection_name,
                    "timestamp": item.get("timestamp") or item.get("run_at") or item.get("started_at"),
                    "title": str(
                        item.get("event")
                        or item.get("sender")
                        or item.get("task_id")
                        or item.get("run_id")
                        or collection_name
                    ),
                    "summary": item.get("logger")
                    or item.get("status")
                    or item.get("content")
                    or item.get("reply_preview"),
                    "fields": item,
                }
            )

    timeline.sort(key=lambda item: str(item.get("timestamp") or ""), reverse=True)
    return timeline[:80]


def build_ops_snapshot(
    *,
    filter_text: str | None,
    selected_run_id: str | None,
    channels: list[dict[str, object]],
    registered_groups: list[dict[str, object]],
    queues: list[dict[str, object]],
    scheduled_tasks: list[dict[str, object]],
    task_runs: list[dict[str, object]],
    sessions: list[dict[str, object]],
    recent_messages: list[dict[str, object]],
    chats: list[dict[str, object]],
    recent_events: list[dict[str, object]],
    agent_runs: list[dict[str, object]],
) -> dict[str, object]:
    query = (filter_text or "").strip().lower()
    selected_run = next(
        (run for run in reversed(agent_runs) if run.get("run_id") == selected_run_id),
        None,
    )
    visible_agent_runs = _filter_items(agent_runs, query)

    return {
        "filter": filter_text or "",
        "selected_run_id": selected_run_id or "",
        "summary": _derive_ops_summary(
            channels=channels,
            queues=queues,
            scheduled_tasks=scheduled_tasks,
            recent_events=recent_events,
            agent_runs=agent_runs,
        ),
        "graph": _build_graph_snapshot(
            channels=channels,
            queues=queues,
            scheduled_tasks=scheduled_tasks,
            recent_messages=recent_messages,
            recent_events=recent_events,
            agent_runs=agent_runs,
        ),
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
        "trace_timeline": _build_timeline(
            query=query,
            selected_run=selected_run,
            recent_events=recent_events,
            recent_messages=recent_messages,
            task_runs=task_runs,
            agent_runs=agent_runs,
        ),
    }
