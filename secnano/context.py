"""Project-level runtime context helpers."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class ProjectContext:
    """Resolved filesystem context for this repository."""

    project_root: Path
    venv_dir: Path
    refs_dir: Path
    packages_dir: Path

    @property
    def venv_python(self) -> Path:
        return self.venv_dir / "bin" / "python"


def load_context() -> ProjectContext:
    project_root = Path(__file__).resolve().parents[1]
    return ProjectContext(
        project_root=project_root,
        venv_dir=project_root / ".venv",
        refs_dir=project_root / "refs",
        packages_dir=project_root / "packages",
    )
