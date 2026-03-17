"""Bridge helpers for resolving the nanobot runtime."""

from __future__ import annotations

import importlib.util
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any


@dataclass(frozen=True)
class RuntimeBridgeInfo:
    provider: str
    available: bool
    import_location: str | None
    package_location: str

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


def inspect_nanobot_bridge(nanobot_package_dir: Path) -> RuntimeBridgeInfo:
    spec = importlib.util.find_spec("nanobot")
    if spec and spec.origin:
        return RuntimeBridgeInfo(
            provider="python_import",
            available=True,
            import_location=spec.origin,
            package_location=str(nanobot_package_dir),
        )

    return RuntimeBridgeInfo(
        provider="python_import",
        available=False,
        import_location=None,
        package_location=str(nanobot_package_dir),
    )
