from __future__ import annotations

from secnano.ops_view import build_ops_snapshot


def test_build_ops_snapshot_uses_debug_views_without_changing_payload_shape() -> None:
    payload = build_ops_snapshot(
        filter_text="room-1",
        selected_run_id="run-42",
        channels=[{"name": "web", "connected": True, "jid": "web:main"}],
        registered_groups=[],
        queues=[],
        scheduled_tasks=[],
        task_runs=[],
        sessions=[],
        recent_messages=[],
        chats=[],
        recent_events=[],
        agent_runs=[{"kind": "message", "run_id": "run-42", "jid": "room-1"}],
    )

    assert payload["filter"] == "room-1"
    assert payload["selected_run_id"] == "run-42"
    assert payload["agent_runs"][0]["jid"] == "room-1"
    assert payload["selected_agent_run"]["run_id"] == "run-42"
    assert payload["trace_timeline"][0]["kind"] == "agent_run"
