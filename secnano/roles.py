"""Role asset management."""

from __future__ import annotations

import json
import logging
from pathlib import Path
from typing import Any

from secnano.context import ProjectContext
from secnano.models import RoleInfo, TaskArchiveRecord, utc_now_iso

logger = logging.getLogger(__name__)


DEFAULT_ROLE_ASSETS: dict[str, dict[str, str]] = {
    "general_office": {
        "SOUL.md": "# general_office\n\n你是系统总务官，负责处理通用任务并保证输出可追踪。\n",
        "ROLE.md": "# general_office\n\n职责：处理通用任务、协调执行、输出结构化结果。\n",
        "MEMORY.md": "# MEMORY\n\n- 初始记忆：无。\n",
        "POLICY.json": json.dumps(
            {
                "allowed_tools": ["shell", "filesystem"],
                "write_scope": ["workspace"],
                "notes": "Milestone 1 minimal policy",
            },
            ensure_ascii=False,
            indent=2,
        )
        + "\n",
    }
}


def _write_file_if_missing(path: Path, content: str) -> bool:
    if path.exists():
        return False
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")
    return True


def ensure_default_roles(ctx: ProjectContext) -> dict[str, int]:
    created_roles = 0
    created_files = 0
    ctx.roles_dir.mkdir(parents=True, exist_ok=True)

    for role_name, assets in DEFAULT_ROLE_ASSETS.items():
        role_dir = ctx.roles_dir / role_name
        role_was_missing = not role_dir.exists()
        role_dir.mkdir(parents=True, exist_ok=True)
        if role_was_missing:
            created_roles += 1
        (role_dir / "skills").mkdir(exist_ok=True)

        for filename, content in assets.items():
            created = _write_file_if_missing(role_dir / filename, content)
            if created:
                created_files += 1

    logger.debug("ensure_default_roles finished created_roles=%s", created_roles)
    return {"created_roles": created_roles, "created_files": created_files}


def list_roles(ctx: ProjectContext) -> list[RoleInfo]:
    if not ctx.roles_dir.exists():
        return []

    roles: list[RoleInfo] = []
    for role_dir in sorted(path for path in ctx.roles_dir.iterdir() if path.is_dir()):
        roles.append(
            RoleInfo(
                name=role_dir.name,
                path=str(role_dir),
                has_role_md=(role_dir / "ROLE.md").exists(),
            )
        )
    return roles


def role_exists(ctx: ProjectContext, role_name: str) -> bool:
    role_dir = ctx.roles_dir / role_name
    return role_dir.is_dir() and (role_dir / "ROLE.md").exists()


def _read_text(path: Path) -> str | None:
    if not path.exists():
        return None
    return path.read_text(encoding="utf-8")


def get_role_assets(ctx: ProjectContext, role_name: str) -> dict[str, Any] | None:
    role_dir = ctx.roles_dir / role_name
    if not role_dir.is_dir():
        return None

    skills_dir = role_dir / "skills"
    skills = sorted(path.name for path in skills_dir.glob("*") if path.is_file())
    payload = {
        "name": role_name,
        "path": str(role_dir),
        "soul": _read_text(role_dir / "SOUL.md"),
        "role": _read_text(role_dir / "ROLE.md"),
        "memory": _read_text(role_dir / "MEMORY.md"),
        "policy": _read_text(role_dir / "POLICY.json"),
        "skills": skills,
    }
    return payload


def promote_memory(
    ctx: ProjectContext,
    *,
    role_name: str,
    record: TaskArchiveRecord,
) -> dict[str, Any]:
    role_dir = ctx.roles_dir / role_name
    if not role_dir.is_dir():
        raise FileNotFoundError(f"role not found: {role_name}")

    memory_path = role_dir / "MEMORY.md"
    if not memory_path.exists():
        memory_path.write_text("# MEMORY\n\n", encoding="utf-8")

    existing = memory_path.read_text(encoding="utf-8")
    marker = f"- task_id: `{record.task_id}`"
    if marker in existing:
        return {
            "role": role_name,
            "memory_path": str(memory_path),
            "task_id": record.task_id,
            "updated": False,
            "reason": "already_promoted",
        }

    summary = record.output.replace("\n", " ").strip()
    if len(summary) > 200:
        summary = summary[:200] + "..."

    entry = (
        f"\n## {utc_now_iso()}\n\n"
        f"- task_id: `{record.task_id}`\n"
        f"- backend: `{record.backend}`\n"
        f"- status: `{record.status}`\n"
        f"- task: {record.task}\n"
        f"- summary: {summary}\n"
    )
    with memory_path.open("a", encoding="utf-8") as handle:
        handle.write(entry)

    return {
        "role": role_name,
        "memory_path": str(memory_path),
        "task_id": record.task_id,
        "updated": True,
        "reason": "appended",
    }
