"""
Local CLI channel for learning and debugging the extracted Python runtime.
"""
from __future__ import annotations

import asyncio
import sys
import uuid
from datetime import datetime, timezone
from typing import Callable, Optional

from ..config import (
    LOCAL_CHANNEL_ENABLED,
    LOCAL_CLI_SENDER_ID,
    LOCAL_CLI_SENDER_NAME,
    LOCAL_MAIN_CHAT_JID,
    LOCAL_MAIN_GROUP_NAME,
)
from ..logger import logger
from ..types import NewMessage
from .base import BaseChannel, OnChatMetadata, OnInboundMessage
from .registry import register_channel


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


class CliChannel(BaseChannel):
    name = "local-cli"

    def __init__(
        self,
        on_message: OnInboundMessage,
        on_chat_metadata: Optional[OnChatMetadata] = None,
        registered_groups: Optional[Callable[[], dict]] = None,
    ) -> None:
        super().__init__(on_message, on_chat_metadata, registered_groups)
        self._connected = False
        self._reader_task: Optional[asyncio.Task] = None
        self._chat_jid = LOCAL_MAIN_CHAT_JID

    async def connect(self) -> None:
        if self._connected:
            return
        self._connected = True
        if self._on_chat_metadata:
            self._on_chat_metadata(
                self._chat_jid,
                _now_iso(),
                LOCAL_MAIN_GROUP_NAME,
                self.name,
                False,
            )
        self._reader_task = asyncio.create_task(self._read_loop())
        sys.stdout.write(
            "Local CLI channel ready. Type a message and press Enter. Ctrl+C or /quit exits.\n"
        )
        sys.stdout.flush()
        logger.info(f"CLI channel connected jid={self._chat_jid}")

    async def _read_loop(self) -> None:
        while self._connected:
            try:
                line = await asyncio.to_thread(input, "You> ")
            except EOFError:
                logger.info("CLI stdin closed")
                self._connected = False
                break
            except Exception as exc:
                logger.error(f"CLI input error: {exc}")
                self._connected = False
                break

            text = line.strip()
            if not text:
                continue
            if text.lower() in {"/quit", "/exit"}:
                logger.info("CLI exit requested")
                self._connected = False
                break

            if self._on_chat_metadata:
                self._on_chat_metadata(
                    self._chat_jid,
                    _now_iso(),
                    LOCAL_MAIN_GROUP_NAME,
                    self.name,
                    False,
                )

            self._on_message(
                self._chat_jid,
                NewMessage(
                    id=str(uuid.uuid4()),
                    chat_jid=self._chat_jid,
                    sender=LOCAL_CLI_SENDER_ID,
                    sender_name=LOCAL_CLI_SENDER_NAME,
                    content=text,
                    timestamp=_now_iso(),
                ),
            )

        logger.info("CLI input loop stopped")

    async def send_message(self, jid: str, text: str) -> None:
        if not text:
            return
        sys.stdout.write(f"Assistant> {text}\n")
        sys.stdout.flush()

    def is_connected(self) -> bool:
        return self._connected

    def owns_jid(self, jid: str) -> bool:
        return jid == self._chat_jid

    async def disconnect(self) -> None:
        self._connected = False
        if self._reader_task and not self._reader_task.done():
            self._reader_task.cancel()
            try:
                await self._reader_task
            except asyncio.CancelledError:
                pass

    async def set_typing(self, jid: str, is_typing: bool) -> None:
        if is_typing:
            sys.stdout.write("Agent> thinking...\n")
            sys.stdout.flush()


register_channel(
    "local-cli",
    lambda on_message, on_chat_metadata=None, registered_groups=None: (
        CliChannel(on_message, on_chat_metadata, registered_groups)
        if LOCAL_CHANNEL_ENABLED
        else None
    ),
)