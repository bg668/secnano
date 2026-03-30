from __future__ import annotations

from pathlib import Path
from types import SimpleNamespace

import pytest

import secnano.db as db_mod
from secnano.db import init_database, list_trace_events
from secnano.runtime import SubprocessRuntimeAdapter
from secnano.trace import TraceStore
from secnano.types import AgentInput, AgentOutput, RegisteredGroup, SubprocessOutput, TraceEvent


def _reset_db(tmp_path: Path) -> None:
    if db_mod._conn is not None:
        db_mod._conn.close()
        db_mod._conn = None
    init_database(tmp_path / "secnano.db")


def test_trace_store_persists_event_to_ring_buffer_and_sqlite(tmp_path: Path) -> None:
    _reset_db(tmp_path)
    store = TraceStore(buffer_size=4)
    event = TraceEvent(
        event_id="evt-1",
        trace_id="trace-1",
        timestamp="2026-03-30T00:00:00+00:00",
        category="message",
        stage="message.received",
        status="accepted",
        jid="room@jid",
        group_folder="room",
        details={"source": "test"},
    )

    store.record(event)

    recent = store.list_recent()
    persisted = list_trace_events(trace_id="trace-1")

    assert [item.stage for item in recent] == ["message.received"]
    assert [item.stage for item in persisted] == ["message.received"]
    assert persisted[0].details == {"source": "test"}


@pytest.mark.asyncio
async def test_subprocess_runtime_adapter_maps_agent_contract(monkeypatch: pytest.MonkeyPatch) -> None:
    captured: dict[str, object] = {}

    async def fake_run_subprocess_agent(group, input_data, on_process, on_output=None):
        captured["group"] = group
        captured["input_data"] = input_data
        on_process(SimpleNamespace(pid=321, returncode=None), "agent-room", group.folder)
        output = SubprocessOutput(status="success", result="done", new_session_id="session-2")
        if on_output is not None:
            await on_output(output)
        return output

    monkeypatch.setattr("secnano.runtime.run_subprocess_agent", fake_run_subprocess_agent)

    adapter = SubprocessRuntimeAdapter()
    observed_outputs: list[AgentOutput] = []
    group = RegisteredGroup(
        jid="room@jid",
        name="Room",
        folder="room",
        trigger="@Andy",
        added_at="2026-03-30T00:00:00+00:00",
    )
    async def on_output(output: AgentOutput) -> None:
        observed_outputs.append(output)

    result = await adapter.run(
        group=group,
        agent_input=AgentInput(
            run_id="run-1",
            trace_id="trace-1",
            group_folder="room",
            chat_jid="room@jid",
            is_main=False,
            mode="message",
            prompt="hello",
            session_id="session-1",
        ),
        on_process=lambda proc, name, folder: captured.update(
            {"process": proc.pid, "subprocess_name": name, "process_folder": folder}
        ),
        on_output=on_output,
    )

    assert captured["group"] == group
    assert captured["input_data"].prompt == "hello"
    assert captured["input_data"].chat_jid == "room@jid"
    assert captured["input_data"].session_id == "session-1"
    assert captured["input_data"].is_scheduled_task is False
    assert captured["subprocess_name"] == "agent-room"
    assert result.status == "success"
    assert result.reply_text == "done"
    assert result.session_id == "session-2"
    assert [item.reply_text for item in observed_outputs] == ["done"]
