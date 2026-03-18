"""子进程通信协议定义。

通信方式：stdin/stdout jsonlines（参考 nanoclaw ContainerInput/ContainerOutput，
但简化为一行一个 JSON，无需 sentinel markers）。

主控 → worker: stdin 写一行 WorkerInput JSON，然后 close stdin
worker → 主控: stdout 写多行 WorkerMessage JSON（每行一个）
worker stderr: 仅日志，主控可选读取
"""

from __future__ import annotations

import json
from dataclasses import asdict, dataclass, field
from typing import Any


@dataclass(frozen=True)
class WorkerInput:
    """主控发给 worker 的任务描述（通过 stdin 发送）。

    对应 nanoclaw ContainerInput 接口（container-runner.ts L38-49），
    但去掉了 Docker 特有字段（sessionId, groupFolder, chatJid, isMain）。
    """

    task_id: str
    role: str              # 角色名（如 general_office）
    task: str              # 用户任务描述
    workspace: str         # 工作目录绝对路径
    role_dir: str          # 角色定义目录路径（含 ROLE.md, SOUL.md, POLICY.json, MEMORY.md）
    timeout: int = 300     # 秒
    max_iterations: int = 15  # agent loop 最大迭代次数
    model: str = ""        # LLM 模型名，空串表示用默认
    provider_env_key: str = "ANTHROPIC_API_KEY"  # API key 的环境变量名

    def to_json_line(self) -> str:
        return json.dumps(asdict(self), ensure_ascii=False)


@dataclass(frozen=True)
class WorkerMessage:
    """Worker 发给主控的消息（通过 stdout 发送，每行一个 JSON）。

    对应 nanoclaw ContainerOutput 接口（container-runner.ts L51-56），
    但拆分为多种 type 支持流式中间输出（nanoclaw 通过多次 OUTPUT_MARKER 对实现同等效果）。

    type 取值：
      "progress"  → 中间进度文本
      "tool_call" → 工具调用记录，metadata 含 {"tool": "exec", "args": {...}}
      "result"    → 最终结果
      "error"     → 错误信息
    """

    type: str
    task_id: str
    content: str = ""
    metadata: dict[str, Any] = field(default_factory=dict)

    def to_json_line(self) -> str:
        return json.dumps(asdict(self), ensure_ascii=False)

    @classmethod
    def from_json_line(cls, line: str) -> "WorkerMessage":
        data = json.loads(line)
        return cls(**data)
