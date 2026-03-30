"""
Channel registration and lookup system.
"""

from __future__ import annotations

from secnano.logger import get_logger
from secnano.types import Channel

log = get_logger("channels.registry")

_registry: dict[str, Channel] = {}


def register_channel(channel: Channel) -> None:
    """Register *channel* by its name."""
    if channel.name in _registry:
        log.warning("Overwriting existing channel registration", name=channel.name)
    _registry[channel.name] = channel
    log.info("Channel registered", name=channel.name)

def list_channels() -> list[Channel]:
    """Return all registered channels."""
    return list(_registry.values())
