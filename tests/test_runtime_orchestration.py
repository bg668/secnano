from __future__ import annotations

from datetime import UTC, datetime
from pathlib import Path
from types import SimpleNamespace

import secnano.db as db_mod
from secnano.db import get_session, init_database, upsert_registered_group
from secnano.types import AgentOutput, RegisteredGroup, ScheduledTask, Session


def _reset_db(tmp_path: Path) -> None:
    if db_mod._conn is not None:
        db_mod._conn.close()
        db_mod._conn = None
    init_database(tmp_path / "secnano.db")


async def test_runtime_orchestrator_handles_scheduled_task_via_adapter(tmp_path: Path) -> None:
    from secnano.runtime_orchestration import RuntimeOrchestrator

    _reset_db(tmp_path)
    now = datetime.now(UTC).isoformat()
    upsert_registered_group(
        RegisteredGroup(
            jid="main@jid",
            name="Main",
            folder="main",
            trigger="@Andy",
            added_at=now,
            is_main=True,
        )
    )

    sent_messages: list[str] = []
    close_calls: list[str] = []
    recorded_runs: list[dict[str, object]] = []

    class FakeRuntimeAdapter:
        async def run(self, *, group, agent_input, on_process, on_output=None):
            on_process(SimpleNamespace(pid=222, returncode=None), "agent-main", group.folder)
            output = AgentOutput(
                run_id=agent_input.run_id,
                status="success",
                reply_text="scheduled-done",
                session_id="session-42",
            )
            if on_output is not None:
                await on_output(output)
            return output

    class DummyChannel:
        async def send_message(self, jid: str, text: str) -> None:
            sent_messages.append(text)

        async def set_typing(self, jid: str, is_typing: bool) -> None:
            return

    class FakeGroupQueue:
        def register_process(self, jid: str, proc, name: str, folder: str) -> None:
            return

        async def close_stdin(self, jid: str) -> None:
            close_calls.append(jid)

        def notify_idle(self, jid: str) -> None:
            return

    orchestrator = RuntimeOrchestrator(
        runtime_adapter=FakeRuntimeAdapter(),
        group_queue=FakeGroupQueue(),
        channels=[DummyChannel()],
        now_utc=lambda: now,
        get_session_id=lambda folder: None,
        save_session=lambda folder, session_id: db_mod.upsert_session(
            Session(
                group_folder=folder,
                session_id=session_id,
                history_path=str(tmp_path / "history.json"),
                updated_at=now,
            )
        ),
        store_bot_message=lambda chat_jid, text, group_folder: None,
        record_agent_run=recorded_runs.append,
        list_registered_groups=db_mod.list_registered_groups,
        format_outbound=lambda text: text,
        truncate=lambda text, limit=240: text,
        log=SimpleNamespace(info=lambda *a, **k: None, error=lambda *a, **k: None),
        find_channel=lambda channels, jid: channels[0],
    )

    result = await orchestrator.handle_scheduled_task(
        ScheduledTask(
            id="task-1",
            group_folder="main",
            chat_jid="main@jid",
            prompt="run this",
            schedule_type="once",
            schedule_value=now,
            context_mode="group",
            next_run=now,
            last_run=None,
            last_result=None,
            status="active",
            created_at=now,
        )
    )

    assert result == "scheduled-done"
    assert sent_messages == ["scheduled-done"]
    assert close_calls == ["main@jid"]
    assert get_session("main") is not None
    assert recorded_runs[-1]["reply_preview"] == "scheduled-done"
