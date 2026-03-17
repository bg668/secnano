"""
NanoClaw Python — Configuration
Mirrors src/config.ts (Path A: container execution preserved).
"""
from __future__ import annotations

import os
import re
from pathlib import Path
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from .env import read_env_file
from .paths import CONFIG_DIR, CONTAINER_DIR, DATA_DIR, GROUPS_DIR, PROJECT_ROOT, STORE_DIR

# ---------------------------------------------------------------------------
# Runtime config (read from .env, then process env)
# ---------------------------------------------------------------------------

_env = read_env_file(
    [
        "ASSISTANT_NAME",
        "ASSISTANT_HAS_OWN_NUMBER",
        "CONTAINER_IMAGE",
        "CONTAINER_RUNTIME",
        "CONTAINER_TIMEOUT",
        "CONTAINER_MAX_OUTPUT_SIZE",
        "IDLE_TIMEOUT",
        "MAX_CONCURRENT_CONTAINERS",
        "TZ",
        "CONTAINER_NAME_PREFIX",
        "LOCAL_CHANNEL_ENABLED",
        "AUTO_REGISTER_LOCAL_MAIN",
        "LOCAL_AGENT_RUNNER",
        "LOCAL_MAIN_CHAT_JID",
        "LOCAL_MAIN_GROUP_NAME",
        "LOCAL_MAIN_GROUP_FOLDER",
        "LOCAL_CLI_SENDER_ID",
        "LOCAL_CLI_SENDER_NAME",
        "NAOCLAW_PY_MOUNT_ALLOWLIST",
        "NAOCLAW_PY_SENDER_ALLOWLIST",
        "NAOCLAW_PY_MOCK_AGENT",
        "ANTHROPIC_MODEL",
        "AGENT_MAX_TOKENS",
        "AGENT_MAX_TURNS",
    ]
)


def _get_env(name: str, default: str) -> str:
    value = os.environ.get(name)
    if value not in (None, ""):
        return value
    value = _env.get(name)
    if value not in (None, ""):
        return value
    return default


def _get_bool(name: str, default: bool) -> bool:
    raw = _get_env(name, "true" if default else "false")
    return raw.strip().lower() in {"1", "true", "yes", "on"}

ASSISTANT_NAME: str = _get_env("ASSISTANT_NAME", "Andy")
ASSISTANT_HAS_OWN_NUMBER: bool = _get_bool("ASSISTANT_HAS_OWN_NUMBER", False)

POLL_INTERVAL: float = 2.0  # seconds
SCHEDULER_POLL_INTERVAL: float = 60.0  # seconds

# ---------------------------------------------------------------------------
# Absolute paths
# ---------------------------------------------------------------------------

MOUNT_ALLOWLIST_PATH = Path(
    _get_env(
        "NAOCLAW_PY_MOUNT_ALLOWLIST",
        str(CONFIG_DIR / "mount-allowlist.json"),
    )
).expanduser().resolve()
SENDER_ALLOWLIST_PATH = Path(
    _get_env(
        "NAOCLAW_PY_SENDER_ALLOWLIST",
        str(CONFIG_DIR / "sender-allowlist.json"),
    )
).expanduser().resolve()

# ---------------------------------------------------------------------------
# Container settings
# ---------------------------------------------------------------------------

CONTAINER_IMAGE: str = _get_env("CONTAINER_IMAGE", "naoclaw-py-agent:latest")
CONTAINER_RUNTIME_BIN: str = _get_env("CONTAINER_RUNTIME", "docker")
CONTAINER_NAME_PREFIX: str = _get_env("CONTAINER_NAME_PREFIX", "naoclaw-py")

CONTAINER_TIMEOUT: int = int(_get_env("CONTAINER_TIMEOUT", "1800000"))  # ms
CONTAINER_MAX_OUTPUT_SIZE: int = int(_get_env("CONTAINER_MAX_OUTPUT_SIZE", "10485760"))
IPC_POLL_INTERVAL: float = 1.0  # seconds
IDLE_TIMEOUT: int = int(_get_env("IDLE_TIMEOUT", "1800000"))  # ms
MAX_CONCURRENT_CONTAINERS: int = max(
    1, int(_get_env("MAX_CONCURRENT_CONTAINERS", "5"))
)
MOCK_AGENT_ENABLED: bool = _get_bool("NAOCLAW_PY_MOCK_AGENT", False)
ANTHROPIC_MODEL: str = _get_env("ANTHROPIC_MODEL", "")
AGENT_MAX_TOKENS: str = _get_env("AGENT_MAX_TOKENS", "")
AGENT_MAX_TURNS: str = _get_env("AGENT_MAX_TURNS", "")

# ---------------------------------------------------------------------------
# Local CLI debug channel
# ---------------------------------------------------------------------------

LOCAL_CHANNEL_ENABLED: bool = _get_bool("LOCAL_CHANNEL_ENABLED", True)
AUTO_REGISTER_LOCAL_MAIN: bool = _get_bool("AUTO_REGISTER_LOCAL_MAIN", True)
LOCAL_AGENT_RUNNER: bool = _get_bool("LOCAL_AGENT_RUNNER", False)
LOCAL_MAIN_CHAT_JID: str = _get_env("LOCAL_MAIN_CHAT_JID", "local://main")
LOCAL_MAIN_GROUP_NAME: str = _get_env("LOCAL_MAIN_GROUP_NAME", "Local Main")
LOCAL_MAIN_GROUP_FOLDER: str = _get_env("LOCAL_MAIN_GROUP_FOLDER", "main")
LOCAL_CLI_SENDER_ID: str = _get_env("LOCAL_CLI_SENDER_ID", "local-user")
LOCAL_CLI_SENDER_NAME: str = _get_env("LOCAL_CLI_SENDER_NAME", "You")

# ---------------------------------------------------------------------------
# Trigger pattern
# ---------------------------------------------------------------------------


def _escape_regex(s: str) -> str:
    return re.escape(s)


TRIGGER_PATTERN: re.Pattern[str] = re.compile(
    rf"^@{_escape_regex(ASSISTANT_NAME)}\b", re.IGNORECASE
)

# ---------------------------------------------------------------------------
# Timezone
# ---------------------------------------------------------------------------

_tz_name = _get_env("TZ", "UTC")
try:
    TIMEZONE: ZoneInfo = ZoneInfo(_tz_name)
except ZoneInfoNotFoundError:
    TIMEZONE = ZoneInfo("UTC")
