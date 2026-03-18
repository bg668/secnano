from __future__ import annotations

from pathlib import Path

from src.v2.schemas.roles import RoleSpec
from src.v2.tongzhengsi.errors import IngressError


class RoleLoadError(IngressError):
    code = "role_load_error"


def _read_required(path: Path) -> str:
    if not path.exists():
        raise RoleLoadError(f"missing required role file: {path.name}")
    return path.read_text(encoding="utf-8").strip()


def load_role_spec(role_name: str, roles_root: Path | None = None) -> RoleSpec:
    root = roles_root or Path("roles")
    role_dir = root / role_name
    if not role_dir.exists():
        raise RoleLoadError(f"role not found: {role_name}")
    return RoleSpec(
        name=role_name,
        soul=_read_required(role_dir / "SOUL"),
        role=_read_required(role_dir / "ROLE"),
        memory=_read_required(role_dir / "MEMORY"),
        policy=_read_required(role_dir / "POLICY"),
    )
