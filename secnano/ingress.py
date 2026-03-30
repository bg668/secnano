"""
Host-side ingress handlers for messages and chat metadata.
"""

from __future__ import annotations

import uuid
from collections.abc import Awaitable, Callable

from secnano.db import (
    get_chat,
    get_registered_group_by_jid,
    insert_message,
    store_chat_metadata,
)
from secnano.types import ChatMetadata, Message, NewMessage, RegisteredGroup

EmitTraceFn = Callable[..., None]
NowFn = Callable[[], str]
SenderAllowedFn = Callable[[str], bool]
MatchesGroupTriggerFn = Callable[[RegisteredGroup, str], bool]
ProcessGroupMessagesFn = Callable[[RegisteredGroup, list[Message], str | None], Awaitable[None]]
EnqueueTaskFn = Callable[[str, str, Callable[[], Awaitable[None]]], Awaitable[None]]
LoggerLike = object


async def handle_chat_metadata(metadata: ChatMetadata, *, now_utc: NowFn) -> None:
    """Persist chat metadata without triggering routing."""
    if not metadata.chat_jid:
        return

    store_chat_metadata(
        chat_jid=metadata.chat_jid,
        timestamp=metadata.timestamp or now_utc(),
        name=metadata.name,
        channel=metadata.channel,
        is_group=metadata.is_group,
    )


async def handle_new_message(
    new_msg: NewMessage,
    *,
    log: LoggerLike,
    now_utc: NowFn,
    emit_trace: EmitTraceFn,
    sender_allowed: SenderAllowedFn,
    matches_group_trigger: MatchesGroupTriggerFn,
    process_group_messages: ProcessGroupMessagesFn,
    enqueue_task: EnqueueTaskFn,
) -> None:
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
    emit_trace(
        trace_id=trace_id,
        category="message",
        stage="message.received",
        status="accepted",
        jid=new_msg.chat_jid,
        details={"sender": new_msg.sender},
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

    if not sender_allowed(new_msg.sender):
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

    existing_chat = get_chat(new_msg.chat_jid)
    store_chat_metadata(
        chat_jid=new_msg.chat_jid,
        timestamp=new_msg.timestamp or now_utc(),
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
            timestamp=new_msg.timestamp or now_utc(),
        )
    )
    log.info(
        "Inbound message stored",
        flow="message",
        stage="stored",
        trace_id=trace_id,
        jid=new_msg.chat_jid,
    )
    emit_trace(
        trace_id=trace_id,
        category="message",
        stage="message.stored",
        status="success",
        jid=new_msg.chat_jid,
    )

    matched = get_registered_group_by_jid(new_msg.chat_jid)
    if matched is None:
        log.info(
            "Inbound message stored without registered group",
            flow="message",
            stage="no_registered_group",
            trace_id=trace_id,
            jid=new_msg.chat_jid,
        )
        emit_trace(
            trace_id=trace_id,
            category="message",
            stage="message.no_registered_group",
            status="skip",
            jid=new_msg.chat_jid,
        )
        return

    emit_trace(
        trace_id=trace_id,
        category="message",
        stage="message.group_matched",
        status="success",
        jid=matched.jid,
        group_folder=matched.folder,
    )

    if not matches_group_trigger(matched, new_msg.content):
        log.info(
            "Inbound message did not match trigger",
            flow="message",
            stage="trigger_miss",
            trace_id=trace_id,
            jid=new_msg.chat_jid,
            group_folder=matched.folder,
        )
        emit_trace(
            trace_id=trace_id,
            category="message",
            stage="message.trigger_miss",
            status="skip",
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
    emit_trace(
        trace_id=trace_id,
        category="message",
        stage="message.enqueued",
        status="accepted",
        jid=matched.jid,
        group_folder=matched.folder,
    )

    async def _run() -> None:
        await process_group_messages(matched, [], trace_id=trace_id)

    await enqueue_task(new_msg.chat_jid, str(uuid.uuid4()), _run)
