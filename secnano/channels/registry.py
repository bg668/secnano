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


def get_channel(name: str) -> Channel | None:
    """Return the channel registered under *name*, or ``None``."""
    return _registry.get(name)


def list_channels() -> list[Channel]:
    """Return all registered channels."""
    return list(_registry.values())


def unregister_channel(name: str) -> None:
    """Remove the channel with *name* from the registry."""
    _registry.pop(name, None)


def clear_registry() -> None:
    """Remove all registered channels (mainly for testing)."""
    _registry.clear()
