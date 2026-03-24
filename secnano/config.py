"""
Configuration constants for secnano.

Values are read from the .env file (without polluting os.environ)
and from the actual process environment as a fallback.
"""

from __future__ import annotations

import os
import re
from pathlib import Path

from secnano.env import read_env_file

# Load .env values (does NOT set os.environ)
_env = read_env_file()


def _get(key: str, default: str = "") -> str:
    """Return value from .env file, falling back to os.environ, then default."""
    return _env.get(key) or os.environ.get(key, default)


# ── Identity ──────────────────────────────────────────────────────────────────
ASSISTANT_NAME: str = _get("ASSISTANT_NAME", "Andy")

# ── Paths ─────────────────────────────────────────────────────────────────────
PROJECT_ROOT: Path = Path.cwd()
HOME_DIR: Path = Path.home()
STORE_DIR: Path = PROJECT_ROOT / "store"
GROUPS_DIR: Path = PROJECT_ROOT / "groups"
DATA_DIR: Path = PROJECT_ROOT / "data"

# ── Polling intervals (seconds) ───────────────────────────────────────────────
POLL_INTERVAL: float = 2.0
SCHEDULER_POLL_INTERVAL: float = 60.0
IPC_POLL_INTERVAL: float = 1.0

# ── Subprocess settings ───────────────────────────────────────────────────────
SUBPROCESS_TIMEOUT: int = int(_get("SUBPROCESS_TIMEOUT", "1800"))  # 30 minutes
MAX_CONCURRENT_SUBPROCESSES: int = int(_get("MAX_CONCURRENT_SUBPROCESSES", "5"))
IDLE_TIMEOUT: int = 1800  # seconds before an idle subprocess is considered stale

# ── Trigger pattern ───────────────────────────────────────────────────────────
# Matches messages that start with "@<AssistantName>" or just the assistant name
_raw_trigger = re.escape(ASSISTANT_NAME)
TRIGGER_PATTERN: re.Pattern[str] = re.compile(rf"(?i)^@?{_raw_trigger}\b")

# ── Anthropic model ───────────────────────────────────────────────────────────
ANTHROPIC_MODEL: str = _get("ANTHROPIC_MODEL", "claude-opus-4-5")

# ── IPC directory structure ───────────────────────────────────────────────────
IPC_DIR: Path = DATA_DIR / "ipc"
SESSIONS_DIR: Path = DATA_DIR / "sessions"

# ── Database ──────────────────────────────────────────────────────────────────
DB_PATH: Path = DATA_DIR / "secnano.db"
