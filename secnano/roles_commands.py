"""CLI command handlers for roles."""

from __future__ import annotations

import json
from dataclasses import asdict

from secnano.context import ProjectContext
from secnano.logging_utils import setup_logging
from secnano.roles import ensure_default_roles, list_roles


def run_roles_ensure_defaults(
    ctx: ProjectContext, *, as_json: bool = False, debug: bool = False
) -> int:
    setup_logging(debug)
    result = ensure_default_roles(ctx)
    if as_json:
        print(json.dumps(result, ensure_ascii=False, indent=2))
    else:
        print(
            f"roles ensure-defaults 完成：created_roles={result['created_roles']} created_files={result['created_files']}"
        )
    return 0


def run_roles_list(ctx: ProjectContext, *, as_json: bool = False, debug: bool = False) -> int:
    setup_logging(debug)
    roles = list_roles(ctx)
    if as_json:
        print(json.dumps([asdict(item) for item in roles], ensure_ascii=False, indent=2))
        return 0

    if not roles:
        print("未发现角色目录。请先执行 `secnano roles ensure-defaults`。")
        return 0

    for role in roles:
        mark = "OK" if role.has_role_md else "WARN"
        print(f"[{mark}] {role.name:<20} {role.path}")
    return 0

