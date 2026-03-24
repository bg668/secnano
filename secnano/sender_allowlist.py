"""
Sender allowlist filtering.

Loads configuration from ~/.config/secnano/sender-allowlist.json.
If the file does not exist, all senders are allowed.
"""

from __future__ import annotations

import json
from pathlib import Path

from secnano.logger import get_logger

log = get_logger("sender_allowlist")

_CONFIG_PATH = Path.home() / ".config" / "secnano" / "sender-allowlist.json"

# Loaded allowlist: None means "allow all"
_allowlist: set[str] | None = None
_loaded = False


def _load() -> None:
    global _allowlist, _loaded
    if _loaded:
        return
    _loaded = True

    if not _CONFIG_PATH.exists():
        _allowlist = None
        return

    try:
        data = json.loads(_CONFIG_PATH.read_text(encoding="utf-8"))
        if isinstance(data, list):
            _allowlist = {str(s).strip() for s in data if s}
            log.info("Sender allowlist loaded", count=len(_allowlist), path=str(_CONFIG_PATH))
        else:
            log.warning(
                "sender-allowlist.json should be a JSON array; allowing all senders",
                path=str(_CONFIG_PATH),
            )
            _allowlist = None
    except (json.JSONDecodeError, OSError) as exc:
        log.error("Failed to load sender allowlist", error=str(exc))
        _allowlist = None


def is_sender_allowed(sender_jid: str) -> bool:
    """
    Return True if *sender_jid* is permitted to trigger the agent.

    If no allowlist file exists, all senders are allowed.
    """
    _load()
    if _allowlist is None:
        return True
    # Normalize: strip @s.whatsapp.net or similar suffixes for comparison
    bare = sender_jid.split("@")[0]
    return sender_jid in _allowlist or bare in _allowlist


def reload() -> None:
    """Force reload of the allowlist from disk."""
    global _loaded
    _loaded = False
    _load()
