from __future__ import annotations

import asyncio
from datetime import UTC, datetime, timedelta
from pathlib import Path
from types import SimpleNamespace

import pytest

import secnano.db as db_mod
import secnano.main as main_mod
import secnano.subprocess_runner as subprocess_runner_mod
import secnano.task_scheduler as scheduler_mod
from secnano.db import (
    get_registered_group,
    init_database,
    insert_message,
    upsert_registered_group,
    upsert_scheduled_task,
)
from secnano.types import IpcTaskRequest, Message, RegisteredGroup, ScheduledTask, SubprocessOutput


def _reset_db(tmp_path: Path) -> None:
    if db_mod._conn is not None:
        db_mod._conn.close()
        db_mod._conn = None
    init_database(tmp_path / "secnano.db")


def test_subprocess_env_includes_anthropic_base_url(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(subprocess_runner_mod, "ANTHROPIC_API_KEY", "test-key")
    monkeypatch.setattr(
        subprocess_runner_mod,
        "ANTHROPIC_BASE_URL",
        "https://coding.dashscope.aliyuncs.com/apps/anthropic",
    )
    monkeypatch.setattr(subprocess_runner_mod, "ANTHROPIC_MODEL", "test-model")

    env = subprocess_runner_mod._build_env("main", "web:main", True)

    assert env["ANTHROPIC_API_KEY"] == "test-key"
    assert env["ANTHROPIC_BASE_URL"] == "https://coding.dashscope.aliyuncs.com/apps/anthropic"
    assert env["ANTHROPIC_MODEL"] == "test-model"


@pytest.mark.asyncio
async def test_register_group_requires_main(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    _reset_db(tmp_path)

    now = datetime.now(UTC).isoformat()
    upsert_registered_group(
        RegisteredGroup(
            jid="main@jid",
            name="main",
            folder="main",
            trigger="@Andy",
            added_at=now,
            is_main=True,
        )
    )
    upsert_registered_group(
        RegisteredGroup(
            jid="worker@jid",
            name="worker",
            folder="worker",
            trigger="@Andy",
            added_at=now,
            is_main=False,
        )
    )

    monkeypatch.setattr(main_mod, "DATA_DIR", tmp_path / "data")
    monkeypatch.setattr(main_mod, "GROUPS_DIR", tmp_path / "groups")

    payload = {
        "type": "register_group",
        "jid": "target@jid",
        "name": "Target Group",
        "folder": "target_group",
        "trigger": "target@jid",
        "timestamp": now,
    }

    # Non-main source should be rejected.
    await main_mod._handle_ipc_task(
        IpcTaskRequest(
            id="task-non-main",
            source_group="worker",
            type="register_group",
            payload=payload,
            timestamp=now,
        )
    )
    assert get_registered_group("target_group") is None

    # Main source should be accepted.
    await main_mod._handle_ipc_task(
        IpcTaskRequest(
            id="task-main",
            source_group="main",
            type="register_group",
            payload=payload,
            timestamp=now,
        )
    )

    registered = get_registered_group("target_group")
    assert registered is not None
    assert registered.jid == "target@jid"
    assert registered.trigger == "target@jid"
    assert (tmp_path / "groups" / "target_group").exists()
    assert (tmp_path / "data" / "ipc" / "target_group" / "tasks").exists()


@pytest.mark.asyncio
async def test_bootstrap_main_group_defaults_to_web_main(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _reset_db(tmp_path)

    monkeypatch.setattr(main_mod, "DATA_DIR", tmp_path / "data")
    monkeypatch.setattr(main_mod, "GROUPS_DIR", tmp_path / "groups")

    group = main_mod._ensure_main_bootstrap()

    assert group.jid == main_mod.DEFAULT_MAIN_JID
    assert group.folder == main_mod.DEFAULT_MAIN_FOLDER
    assert group.is_main is True
    assert group.requires_trigger is False
    assert get_registered_group(main_mod.DEFAULT_MAIN_FOLDER) is not None
    assert (tmp_path / "groups" / main_mod.DEFAULT_MAIN_FOLDER).exists()
    assert (tmp_path / "data" / "ipc" / main_mod.DEFAULT_MAIN_FOLDER / "messages").exists()


@pytest.mark.asyncio
async def test_handle_new_message_routes_by_registered_jid(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _reset_db(tmp_path)

    now = datetime.now(UTC).isoformat()
    upsert_registered_group(
        RegisteredGroup(
            jid="room@jid",
            name="Room",
            folder="room",
            trigger="@Andy",
            added_at=now,
            requires_trigger=False,
            is_main=False,
        )
    )

    enqueued: list[str] = []

    async def fake_enqueue(group_jid: str, task_id: str, fn) -> None:
        enqueued.append(group_jid)

    monkeypatch.setattr(main_mod._group_queue, "enqueue_task", fake_enqueue)

    await main_mod._handle_new_message(
        main_mod.NewMessage(
            id="m1",
            chat_jid="room@jid",
            sender="user@jid",
            sender_name="User",
            content="hello there",
            timestamp=now,
        )
    )

    assert enqueued == ["room@jid"]


@pytest.mark.asyncio
async def test_process_group_messages_closes_typing_and_stdin_early(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _reset_db(tmp_path)
    now = datetime.now(UTC).isoformat()

    monkeypatch.setattr(main_mod, "DATA_DIR", tmp_path / "data")
    monkeypatch.setattr(main_mod, "GROUPS_DIR", tmp_path / "groups")

    insert_message(
        Message(
            id="msg-1",
            chat_jid="web:main",
            sender="user@jid",
            sender_name="User",
            content="hello",
            timestamp=now,
        )
    )

    group = RegisteredGroup(
        jid="web:main",
        name="Main",
        folder="main",
        trigger="@Andy",
        added_at=now,
        requires_trigger=False,
        is_main=True,
    )

    typing_calls: list[bool] = []
    sent_messages: list[str] = []
    close_calls: list[str] = []

    class DummyChannel:
        name = "dummy"

        async def connect(self) -> None:
            return

        async def send_message(self, jid: str, text: str) -> None:
            sent_messages.append(text)

        def is_connected(self) -> bool:
            return True

        def owns_jid(self, jid: str) -> bool:
            return jid == "web:main"

        async def disconnect(self) -> None:
            return

        async def set_typing(self, jid: str, is_typing: bool) -> None:
            typing_calls.append(is_typing)

    async def fake_close_stdin(jid: str) -> None:
        close_calls.append(jid)

    async def fake_run_subprocess_agent(group, input_data, on_process, on_output):
        on_process(SimpleNamespace(pid=123, returncode=None), "agent-main", "main")
        await on_output(
            SubprocessOutput(
                status="success",
                result="done",
                new_session_id="session-1",
            )
        )
        return SubprocessOutput(status="success", result="done", new_session_id="session-1")

    monkeypatch.setattr(main_mod, "_channels", [DummyChannel()])
    monkeypatch.setattr(main_mod._group_queue, "close_stdin", fake_close_stdin)
    monkeypatch.setattr(main_mod, "run_subprocess_agent", fake_run_subprocess_agent)
    main_mod._recent_agent_runs.clear()

    await main_mod._process_group_messages(group, [])

    assert sent_messages == ["done"]
    assert close_calls == ["web:main"]
    assert typing_calls == [True, False]
    assert len(main_mod._recent_agent_runs) == 1
    assert main_mod._recent_agent_runs[-1]["reply_preview"] == "done"


@pytest.mark.asyncio
async def test_scheduler_due_tasks_enqueue_once_while_pending(tmp_path: Path) -> None:
    _reset_db(tmp_path)
    scheduler_mod._queued_task_ids.clear()

    due_time = (datetime.now(UTC) - timedelta(minutes=1)).isoformat()
    task = ScheduledTask(
        id="task-1",
        group_folder="main",
        chat_jid="main@jid",
        prompt="do something",
        schedule_type="once",
        schedule_value=due_time,
        context_mode="group",
        next_run=due_time,
        last_run=None,
        last_result=None,
        status="active",
        created_at=datetime.now(UTC).isoformat(),
    )
    upsert_scheduled_task(task)

    enqueued_runs: list[tuple[ScheduledTask, object]] = []

    async def enqueue(scheduled: ScheduledTask, run) -> None:
        enqueued_runs.append((scheduled, run))

    async def runner(_: ScheduledTask) -> str:
        await asyncio.sleep(0)
        return "ok"

    first = await scheduler_mod._enqueue_due_tasks_once(runner=runner, enqueue=enqueue)
    second = await scheduler_mod._enqueue_due_tasks_once(runner=runner, enqueue=enqueue)

    assert first == 1
    assert second == 0
    assert len(enqueued_runs) == 1

    # Execute queued task wrapper; it should clear in-memory dedupe state.
    await enqueued_runs[0][1]()
    third = await scheduler_mod._enqueue_due_tasks_once(runner=runner, enqueue=enqueue)
    assert third == 0
