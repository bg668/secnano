"""
Host-side control plane handlers.
"""

from __future__ import annotations

from collections.abc import Callable

from secnano.db import get_chat, get_registered_group, store_chat_metadata, upsert_registered_group
from secnano.group_folder import is_valid_group_folder
from secnano.types import IpcTaskRequest, RegisteredGroup

EmitTraceFn = Callable[..., None]
EnsureGroupDirsFn = Callable[[str], None]
NowFn = Callable[[], str]
LoggerLike = object


async def handle_ipc_task(
    task: IpcTaskRequest,
    *,
    log: LoggerLike,
    now_utc: NowFn,
    ensure_group_dirs: EnsureGroupDirsFn,
    emit_trace: EmitTraceFn,
) -> None:
    """Process IPC task requests (currently: register_group)."""
    log.info(
        "IPC task received",
        flow="ipc_task",
        stage="received",
        task_id=task.id,
        source_group=task.source_group,
        type=task.type,
    )
    emit_trace(
        trace_id=task.id,
        category="ipc_task",
        stage="ipc_task.received",
        status="accepted",
        task_id=task.id,
        source=task.source_group,
    )
    if task.type != "register_group":
        log.debug("Ignoring unsupported IPC task type", type=task.type, source_group=task.source_group)
        return

    source = get_registered_group(task.source_group)
    if source is None or not source.is_main:
        emit_trace(
            trace_id=task.id,
            category="ipc_task",
            stage="ipc_task.auth_checked",
            status="rejected",
            task_id=task.id,
            source=task.source_group,
        )
        emit_trace(
            trace_id=task.id,
            category="ipc_task",
            stage="ipc_task.rejected",
            status="rejected",
            task_id=task.id,
            source=task.source_group,
        )
        log.warning(
            "Unauthorized register_group attempt blocked",
            source_group=task.source_group,
            task_id=task.id,
        )
        return

    emit_trace(
        trace_id=task.id,
        category="ipc_task",
        stage="ipc_task.auth_checked",
        status="success",
        task_id=task.id,
        source=task.source_group,
    )

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
        timestamp=task.timestamp or now_utc(),
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
        added_at=now_utc(),
        requires_trigger=requires_trigger,
        is_main=False,
    )
    upsert_registered_group(group)
    ensure_group_dirs(folder)

    log.info(
        "Group registered via IPC task",
        flow="ipc_task",
        stage="completed",
        source_group=task.source_group,
        jid=jid,
        folder=folder,
        trigger=trigger,
    )
    emit_trace(
        trace_id=task.id,
        category="ipc_task",
        stage="ipc_task.group_registered",
        status="success",
        jid=jid,
        group_folder=folder,
        task_id=task.id,
        source=task.source_group,
    )
