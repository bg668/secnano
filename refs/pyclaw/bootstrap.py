"""
Bootstrap helpers for the standalone NanoClaw Python learning repo.
"""
from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

from .config import (
    ASSISTANT_NAME,
    AUTO_REGISTER_LOCAL_MAIN,
    LOCAL_CHANNEL_ENABLED,
    LOCAL_MAIN_CHAT_JID,
    LOCAL_MAIN_GROUP_FOLDER,
    LOCAL_MAIN_GROUP_NAME,
)
from .paths import CONFIG_DIR, DATA_DIR, GROUPS_DIR, STORE_DIR
from .types import RegisteredGroup

_DEFAULT_GLOBAL_CLAUDE = """Global guidance shared by all groups.

Use this file for behavior or memory that should be visible across groups.
"""

_DEFAULT_MAIN_CLAUDE = """Local main group for the extracted NanoClaw Python learning repo.

Use this group to inspect message routing, container execution, and task flow.
"""

_DEFAULT_SENDER_ALLOWLIST = {
    "default": {"allow": "*", "mode": "trigger"},
    "chats": {},
    "logDenied": True,
}

_DEFAULT_MOUNT_ALLOWLIST = {
    "allowedRoots": [
        {"path": "~/Documents", "allowReadWrite": False},
        {"path": "~/Downloads", "allowReadWrite": False},
    ],
    "blockedPatterns": [],
    "nonMainReadOnly": True,
}


def _write_if_missing(path: Path, content: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    if not path.exists():
        path.write_text(content, encoding="utf-8")


def bootstrap_project_layout() -> None:
    for path in (CONFIG_DIR, DATA_DIR, STORE_DIR, GROUPS_DIR, DATA_DIR / "ipc", DATA_DIR / "sessions"):
        path.mkdir(parents=True, exist_ok=True)

    for folder in ("global", "main"):
        (GROUPS_DIR / folder).mkdir(parents=True, exist_ok=True)

    _write_if_missing(GROUPS_DIR / "global" / "CLAUDE.md", _DEFAULT_GLOBAL_CLAUDE)
    _write_if_missing(GROUPS_DIR / "main" / "CLAUDE.md", _DEFAULT_MAIN_CLAUDE)
    _write_if_missing(
        CONFIG_DIR / "sender-allowlist.json",
        json.dumps(_DEFAULT_SENDER_ALLOWLIST, indent=2) + "\n",
    )
    _write_if_missing(
        CONFIG_DIR / "mount-allowlist.json",
        json.dumps(_DEFAULT_MOUNT_ALLOWLIST, indent=2) + "\n",
    )


def build_default_local_group(
    existing_groups: dict[str, RegisteredGroup],
) -> Optional[tuple[str, RegisteredGroup]]:
    if not LOCAL_CHANNEL_ENABLED or not AUTO_REGISTER_LOCAL_MAIN:
        return None
    if LOCAL_MAIN_CHAT_JID in existing_groups:
        return None

    has_main_group = any(group.isMain for group in existing_groups.values())
    return (
        LOCAL_MAIN_CHAT_JID,
        RegisteredGroup(
            name=LOCAL_MAIN_GROUP_NAME,
            folder=LOCAL_MAIN_GROUP_FOLDER,
            trigger=f"@{ASSISTANT_NAME}",
            added_at=datetime.now(timezone.utc).isoformat(),
            requiresTrigger=False,
            isMain=not has_main_group,
        ),
    )