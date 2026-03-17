# secnano

`secnano` 是一个独立的 Python 包与 CLI 工具，目标是以“单一主控 agent + 安全委派”为核心，逐步落地文档中的里程碑能力。

当前已提供的可执行命令：

- `python3 -m secnano --help`
- `python3 -m secnano doctor`
- `python3 -m secnano bootstrap --dry-run`

兼容阶段目录约定：

- `packages/nanobot/`：`nanobot` 上游兼容包
- `refs/pyclaw/`、`refs/nanoclaw/`：执行与安全机制参考实现
