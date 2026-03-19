from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class ProjectPaths:
    root_dir: Path
    runtime_dir: Path
    db_dir: Path
    db_path: Path

    @classmethod
    def discover(cls) -> "ProjectPaths":
        root_dir = Path(__file__).resolve().parent.parent
        runtime_dir = root_dir / "runtime"
        db_dir = runtime_dir / "db"
        db_path = db_dir / "secnano.sqlite3"
        return cls(
            root_dir=root_dir,
            runtime_dir=runtime_dir,
            db_dir=db_dir,
            db_path=db_path,
        )

    def ensure_runtime_dirs(self) -> None:
        self.db_dir.mkdir(parents=True, exist_ok=True)
