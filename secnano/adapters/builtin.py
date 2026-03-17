"""Built-in capability adapters."""

from __future__ import annotations

import importlib.util

from secnano.adapters.base import CapabilitySpec
from secnano.context import ProjectContext


class HostExecutionAdapter:
    adapter_id = "host_execution"
    display_name = "Host Execution Adapter"
    source = "secnano.backends.host"
    description = "提供宿主机最小委派执行能力。"

    def availability(self, ctx: ProjectContext) -> tuple[bool, str]:
        _ = ctx
        return True, "host backend 可用"

    def capabilities(self) -> list[CapabilitySpec]:
        return [
            CapabilitySpec(
                capability_id="host_delegate",
                name="Host Delegate",
                description="在宿主机执行最小委派任务。",
                tools=["delegate_host"],
            )
        ]


class PyclawContainerAdapter:
    adapter_id = "pyclaw_container"
    display_name = "Pyclaw Container Adapter"
    source = "refs/pyclaw + refs/nanoclaw"
    description = "提供容器执行准备链路（validated 阶段）。"

    def availability(self, ctx: ProjectContext) -> tuple[bool, str]:
        pyclaw_ok = (ctx.refs_dir / "pyclaw").exists()
        nanoclaw_ok = (ctx.refs_dir / "nanoclaw").exists()
        if pyclaw_ok and nanoclaw_ok:
            return True, "refs/pyclaw 与 refs/nanoclaw 存在"
        return False, "缺少 refs/pyclaw 或 refs/nanoclaw"

    def capabilities(self) -> list[CapabilitySpec]:
        return [
            CapabilitySpec(
                capability_id="container_delegate_validated",
                name="Container Delegate (Validated)",
                description="容器后端运行时校验与 validated 级委派。",
                tools=["runtime_inspect", "runtime_validate", "delegate_pyclaw_container"],
            )
        ]


class NanobotRuntimeAdapter:
    adapter_id = "nanobot_runtime"
    display_name = "Nanobot Runtime Adapter"
    source = "packages/nanobot"
    description = "兼容阶段的 nanobot 运行时桥接能力。"

    def availability(self, ctx: ProjectContext) -> tuple[bool, str]:
        package_ok = (ctx.packages_dir / "nanobot").exists()
        spec = importlib.util.find_spec("nanobot")
        if package_ok and spec and spec.origin:
            return True, f"已导入 nanobot: {spec.origin}"
        if package_ok:
            return False, "packages/nanobot 存在但未导入"
        return False, "缺少 packages/nanobot"

    def capabilities(self) -> list[CapabilitySpec]:
        return [
            CapabilitySpec(
                capability_id="nanobot_bridge",
                name="Nanobot Runtime Bridge",
                description="兼容阶段运行时桥接检查能力。",
                tools=["doctor_nanobot_bridge"],
            )
        ]

