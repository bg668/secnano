from __future__ import annotations

import asyncio
import json
from urllib import request

import pytest

from secnano.channels.web import LocalWebChannel
from secnano.types import ChatMetadata, Message, NewMessage


async def _urlopen_json(url: str, data: bytes | None = None) -> dict:
    def _run() -> dict:
        req = request.Request(url, data=data)
        if data is not None:
            req.add_header("Content-Type", "application/json")
        with request.urlopen(req, timeout=5) as response:  # noqa: S310
            return json.loads(response.read().decode("utf-8"))

    return await asyncio.to_thread(_run)


@pytest.mark.asyncio
async def test_local_web_channel_round_trip() -> None:
    inbound_messages: list[NewMessage] = []
    metadata_events: list[ChatMetadata] = []

    async def on_message(message: NewMessage) -> None:
        inbound_messages.append(message)

    async def on_chat_metadata(metadata: ChatMetadata) -> None:
        metadata_events.append(metadata)

    history = [
        Message(
            id="h1",
            chat_jid="web:main",
            sender="web-user",
            sender_name="Web User",
            content="history from db",
            timestamp="2026-03-28T00:00:00+00:00",
        ),
        Message(
            id="h2",
            chat_jid="web:main",
            sender="bot",
            sender_name="Main Web Chat",
            content="history reply",
            timestamp="2026-03-28T00:00:01+00:00",
            is_from_me=True,
            is_bot_message=True,
        ),
    ]

    channel = LocalWebChannel(
        on_message=on_message,
        on_chat_metadata=on_chat_metadata,
        host="127.0.0.1",
        port=0,
        chat_jid="web:main",
        chat_name="Main Web Chat",
        history_loader=lambda: history,
    )

    await channel.connect()
    try:
        assert channel.is_connected()
        assert metadata_events
        assert metadata_events[0].chat_jid == "web:main"

        initial = await _urlopen_json(f"{channel.url}/api/messages?since=0")
        initial_texts = [item["text"] for item in initial["messages"]]
        assert "history from db" in initial_texts
        assert "history reply" in initial_texts

        await _urlopen_json(
            f"{channel.url}/api/send",
            data=json.dumps({"text": "hello from browser"}).encode("utf-8"),
        )

        for _ in range(50):
            if inbound_messages:
                break
            await asyncio.sleep(0.02)

        assert inbound_messages
        assert inbound_messages[0].content == "hello from browser"

        await channel.send_message("web:main", "hello from agent")
        payload = await _urlopen_json(f"{channel.url}/api/messages?since=0")
        texts = [item["text"] for item in payload["messages"]]
        assert "hello from browser" in texts
        assert "hello from agent" in texts
        assert payload["chat_jid"] == "web:main"
    finally:
        await channel.disconnect()


@pytest.mark.asyncio
async def test_local_web_channel_ops_endpoint() -> None:
    channel = LocalWebChannel(
        on_message=lambda message: asyncio.sleep(0),
        on_chat_metadata=lambda metadata: asyncio.sleep(0),
        host="127.0.0.1",
        port=0,
        chat_jid="web:main",
        chat_name="Main Web Chat",
        ops_snapshot=lambda q, run: {
            "channels": [{"name": "web", "connected": True, "jid": "web:main"}],
            "registered_groups": [],
            "queues": [],
            "agent_runs": [{"kind": "message", "run_id": run or "run-1", "jid": q or "web:main"}],
            "selected_agent_run": {"run_id": run or "", "jid": q or "web:main"} if run else None,
            "scheduled_tasks": [],
            "task_runs": [],
            "sessions": [],
            "recent_messages": [],
            "chats": [],
            "recent_events": [],
            "trace_timeline": [],
        },
    )

    await channel.connect()
    try:
        payload = await _urlopen_json(f"{channel.url}/api/ops")
        assert payload["enabled"] is True
        assert payload["channels"][0]["jid"] == "web:main"
        assert payload["agent_runs"][0]["jid"] == "web:main"

        filtered = await _urlopen_json(f"{channel.url}/api/ops?q=room-1")
        assert filtered["filter"] == "room-1"
        assert filtered["agent_runs"][0]["jid"] == "room-1"

        selected = await _urlopen_json(f"{channel.url}/api/ops?run=run-42")
        assert selected["selected_run_id"] == "run-42"
        assert selected["selected_agent_run"]["run_id"] == "run-42"
    finally:
        await channel.disconnect()
