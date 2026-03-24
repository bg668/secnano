"""
Message formatting and routing utilities.
"""

from __future__ import annotations

import html
import re
from typing import Optional

from secnano.types import Channel, Message

_INTERNAL_TAG_RE = re.compile(r"<internal>.*?</internal>", re.DOTALL | re.IGNORECASE)


def escape_xml(s: str) -> str:
    """Escape special XML/HTML characters in *s*."""
    return html.escape(s, quote=True)


def format_messages(messages: list[Message], timezone: str = "UTC") -> str:
    """
    Format a list of messages as an XML conversation block.

    Each message is wrapped in a ``<message>`` tag with metadata attributes.
    """
    from secnano.timezone_utils import format_local_time

    parts: list[str] = ["<conversation>"]
    for msg in messages:
        local_time = format_local_time(msg.timestamp, timezone)
        sender_label = "me" if msg.is_from_me else escape_xml(msg.sender_name or msg.sender)
        parts.append(
            f'  <message from="{escape_xml(sender_label)}" time="{escape_xml(local_time)}">'
            f"{escape_xml(msg.content)}"
            f"</message>"
        )
    parts.append("</conversation>")
    return "\n".join(parts)


def strip_internal_tags(text: str) -> str:
    """Remove all ``<internal>…</internal>`` blocks from *text*."""
    return _INTERNAL_TAG_RE.sub("", text).strip()


def format_outbound(text: str) -> str:
    """Prepare agent output for sending to a user (strip internal tags)."""
    return strip_internal_tags(text)


def find_channel(channels: list[Channel], jid: str) -> Optional[Channel]:
    """Return the first channel that owns *jid*, or ``None``."""
    for channel in channels:
        if channel.owns_jid(jid):
            return channel
    return None
