"""
Group folder path validation.

Group folder names serve as workspace identifiers. This module validates
names and resolves safe absolute paths.
"""

from __future__ import annotations

import re
from pathlib import Path

from secnano.config import GROUPS_DIR, IPC_DIR

# Valid folder name: starts with alphanumeric, followed by alphanumeric/dash/underscore
_VALID_PATTERN: re.Pattern[str] = re.compile(r"^[A-Za-z0-9][A-Za-z0-9_-]{0,63}$")

# Names that are reserved and cannot be used as group folders
_RESERVED_NAMES: frozenset[str] = frozenset({"global"})


def is_valid_group_folder(name: str) -> bool:
    """
    Return True if *name* is a valid group folder identifier.

    Rules:
    - Matches ``^[A-Za-z0-9][A-Za-z0-9_-]{0,63}$``
    - Not in the reserved list
    - No path components (no ``/`` or ``..``)
    """
    if not name or "/" in name or "\\" in name:
        return False
    if name in _RESERVED_NAMES:
        return False
    return bool(_VALID_PATTERN.match(name))


def resolve_group_folder_path(folder_name: str, base_dir: Path | None = None) -> Path:
    """
    Resolve the absolute path to a group's workspace directory.

    Raises ``ValueError`` if *folder_name* is invalid or resolves outside *base_dir*.
    """
    if not is_valid_group_folder(folder_name):
        raise ValueError(f"Invalid group folder name: {folder_name!r}")

    base = (base_dir or GROUPS_DIR).resolve()
    resolved = (base / folder_name).resolve()

    # Guard against path-traversal attacks
    if not str(resolved).startswith(str(base) + "/") and resolved != base:
        raise ValueError(f"Path traversal detected for folder name: {folder_name!r}")

    return resolved


def resolve_group_ipc_path(folder_name: str) -> Path:
    """
    Resolve the IPC directory for a group's subprocess communication.

    Raises ``ValueError`` if *folder_name* is invalid.
    """
    if not is_valid_group_folder(folder_name):
        raise ValueError(f"Invalid group folder name: {folder_name!r}")

    ipc_base = IPC_DIR.resolve()
    resolved = (ipc_base / folder_name).resolve()

    if not str(resolved).startswith(str(ipc_base) + "/") and resolved != ipc_base:
        raise ValueError(f"Path traversal detected for IPC folder name: {folder_name!r}")

    return resolved
