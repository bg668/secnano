# secnano

`secnano` 是一个独立的 Python 包与 CLI 工具，目标是以“单一主控 agent + 安全委派”为核心，逐步落地文档中的里程碑能力。

当前已提供的可执行命令（Milestone A 开发启动）：

- `python3 -m secnano --help`
- `python3 -m secnano tasks submit --role general_office --task "..."`
- `python3 -m secnano tasks show <task-id>`
- `python3 -m secnano tasks list --status pending --limit 20`
- `python3 -m secnano tasks poll <task-id> --timeout 120`

兼容阶段目录约定：

- `packages/nanobot/`：`nanobot` 上游兼容包
- `refs/pyclaw/`、`refs/nanoclaw/`：执行与安全机制参考实现
