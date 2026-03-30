"""
Group folder path validation.

Group folder names serve as workspace identifiers. This module validates
names and resolves safe absolute paths.
"""

from __future__ import annotations

import re

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
