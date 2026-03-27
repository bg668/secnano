from __future__ import annotations

import asyncio
from datetime import UTC, datetime, timedelta
from pathlib import Path

import pytest

import secnano.db as db_mod
import secnano.main as main_mod
import secnano.task_scheduler as scheduler_mod
from secnano.db import (
    get_registered_group,
    init_database,
    upsert_registered_group,
    upsert_scheduled_task,
)
from secnano.types import IpcTaskRequest, RegisteredGroup, ScheduledTask


def _reset_db(tmp_path: Path) -> None:
    if db_mod._conn is not None:
        db_mod._conn.close()
        db_mod._conn = None
    init_database(tmp_path / "secnano.db")


@pytest.mark.asyncio
async def test_register_group_requires_main(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    _reset_db(tmp_path)

    now = datetime.now(UTC).isoformat()
    upsert_registered_group(
        RegisteredGroup(
            name="main",
            folder="main",
            trigger="main@jid",
            added_at=now,
            is_main=True,
        )
    )
    upsert_registered_group(
        RegisteredGroup(
            name="worker",
            folder="worker",
            trigger="worker@jid",
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
    assert registered.trigger == "target@jid"
    assert (tmp_path / "groups" / "target_group").exists()
    assert (tmp_path / "data" / "ipc" / "target_group" / "tasks").exists()


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
