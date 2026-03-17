"""CLI command handlers for roles."""

from __future__ import annotations

import json
from dataclasses import asdict

from secnano.archive import TaskArchiveStore
from secnano.context import ProjectContext
from secnano.logging_utils import setup_logging
from secnano.roles import ensure_default_roles, get_role_assets, list_roles, promote_memory


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


def run_roles_show(
    ctx: ProjectContext,
    *,
    role_name: str,
    as_json: bool = False,
    debug: bool = False,
) -> int:
    setup_logging(debug)
    payload = get_role_assets(ctx, role_name)
    if payload is None:
        print(f"角色不存在：{role_name}")
        return 2

    if as_json:
        print(json.dumps(payload, ensure_ascii=False, indent=2))
        return 0

    print(f"role: {payload['name']}")
    print(f"path: {payload['path']}")
    print(f"skills: {len(payload['skills'])}")
    print("--- SOUL ---")
    print(payload["soul"] or "(missing)")
    print("--- ROLE ---")
    print(payload["role"] or "(missing)")
    print("--- MEMORY ---")
    print(payload["memory"] or "(missing)")
    print("--- POLICY ---")
    print(payload["policy"] or "(missing)")
    return 0


def run_roles_promote_memory(
    ctx: ProjectContext,
    *,
    role_name: str,
    task_id: str,
    as_json: bool = False,
    debug: bool = False,
) -> int:
    setup_logging(debug)
    record = TaskArchiveStore(ctx).get_record(task_id)
    if record is None:
        print(f"任务归档不存在：{task_id}")
        return 2

    result = promote_memory(ctx, role_name=role_name, record=record)
    if as_json:
        print(json.dumps(result, ensure_ascii=False, indent=2))
    else:
        print(
            "memory promotion 完成: "
            f"role={result['role']} task_id={result['task_id']} "
            f"updated={result.get('updated', True)} path={result['memory_path']}"
        )
    return 0
