from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class ProjectPaths:
    root_dir: Path
    runtime_dir: Path
    db_dir: Path
    db_path: Path
    ipc_dir: Path
    ipc_errors_dir: Path

    @classmethod
    def discover(cls) -> "ProjectPaths":
        root_dir = Path(__file__).resolve().parent.parent
        runtime_dir = root_dir / "runtime"
        db_dir = runtime_dir / "db"
        db_path = db_dir / "secnano.sqlite3"
        ipc_dir = runtime_dir / "ipc"
        ipc_errors_dir = ipc_dir / "errors"
        return cls(
            root_dir=root_dir,
            runtime_dir=runtime_dir,
            db_dir=db_dir,
            db_path=db_path,
            ipc_dir=ipc_dir,
            ipc_errors_dir=ipc_errors_dir,
        )

    def ensure_runtime_dirs(self) -> None:
        self.db_dir.mkdir(parents=True, exist_ok=True)

    def ensure_ipc_dirs(self, namespace: str) -> None:
        (self.ipc_dir / namespace / "tasks").mkdir(parents=True, exist_ok=True)
        (self.ipc_dir / namespace / "results").mkdir(parents=True, exist_ok=True)
        self.ipc_errors_dir.mkdir(parents=True, exist_ok=True)
