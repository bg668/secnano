"""
Safe .env file reader.

Reads key=value pairs from a .env file WITHOUT loading them into os.environ,
preventing secret leaks to subprocesses that inherit the environment.
"""

from __future__ import annotations

import re
from pathlib import Path

_COMMENT_RE = re.compile(r"^\s*#.*$")
_BLANK_RE = re.compile(r"^\s*$")
_KV_RE = re.compile(r"^\s*([A-Za-z_][A-Za-z0-9_]*)\s*=\s*(.*?)\s*$")


def _strip_quotes(value: str) -> str:
    """Remove surrounding single or double quotes from a value."""
    if len(value) >= 2 and (
        (value[0] == '"' and value[-1] == '"') or (value[0] == "'" and value[-1] == "'")
    ):
        return value[1:-1]
    return value


def read_env_file(path: Path | str | None = None) -> dict[str, str]:
    """
    Parse a .env file and return its contents as a dictionary.

    Does NOT set os.environ — values are returned only to the caller.
    Lines beginning with '#' are treated as comments and ignored.
    Surrounding quotes are stripped from values.

    Args:
        path: Path to the .env file. Defaults to '.env' in the current directory.

    Returns:
        A dict mapping variable names to their string values.
    """
    env_path = Path(path) if path is not None else Path(".env")
    result: dict[str, str] = {}

    if not env_path.exists():
        return result

    for line in env_path.read_text(encoding="utf-8").splitlines():
        if _COMMENT_RE.match(line) or _BLANK_RE.match(line):
            continue
        m = _KV_RE.match(line)
        if m:
            key, raw_value = m.group(1), m.group(2)
            result[key] = _strip_quotes(raw_value)

    return result
