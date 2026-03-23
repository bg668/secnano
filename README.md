# secnano

`secnano` 是一个独立的 Python 包与 CLI 工具，目标是以“单一主控 agent + 安全委派”为核心，逐步落地文档中的里程碑能力。

当前已提供的可执行命令（Milestone B 已完成）：

- `python3 -m secnano --help`
- `python3 -m secnano tasks submit --role general_office --task "..."`
- `python3 -m secnano tasks show <task-id>`
- `python3 -m secnano tasks list --status pending --limit 20`
- `python3 -m secnano tasks poll <task-id> --timeout 120`
- `python3 -m secnano ipc write-task --role general_office --task "..." --namespace main`
- `python3 -m secnano ipc watch --namespace main --json`

兼容阶段目录约定：

- `packages/nanobot/`：`nanobot` 上游兼容包
- `refs/pyclaw/`、`refs/nanoclaw/`：执行与安全机制参考实现

---

## Phase 1 — 主控优先路线（已实现）

### 架构变化

Phase 1 将主控侧升级为三合一 Daemon 架构：

```
workers start
  ├── IPCWatcher  — 持续轮询 IPC 目录，将文件任务写入 DB
  ├── Scheduler   — 按 cron/interval/once 定时触发任务
  └── WorkerPool  — 子进程调度池（claim → spawn → result）
```

**关键技术变化**：
- DB 层从同步 `sqlite3` 迁移到异步 `aiosqlite`
- 新增 `schedule_type / schedule_value / last_run / next_run_at` 调度字段
- 新增 `timeout` / `paused` 任务状态
- WorkerPool 超时后记录 `{pid, duration_ms, last_output}`，状态改为 `timeout`

### CLI 命令（Phase 1 新增）

```bash
# 任务生命周期
python3 -m secnano tasks pause   <task_id>    # 暂停任务
python3 -m secnano tasks resume  <task_id>    # 恢复任务（重置为 pending）
python3 -m secnano tasks cancel  <task_id>    # 取消任务
python3 -m secnano tasks retry   <task_id>    # 重试（创建新 task_id，保留旧任务历史）
python3 -m secnano tasks logs    <task_id>    # 查看运行日志

# 启动三合一 Daemon
python3 -m secnano workers start --max-workers 4 --task-timeout 300 --namespace main
```

### 新增依赖

| 依赖 | 用途 |
|------|------|
| `aiosqlite>=0.19.0` | 异步 SQLite |
| `croniter>=1.4.0`   | cron 表达式解析 |

### 定时任务

创建任务时可通过 `runtime_db` API 指定调度类型：

```python
from secnano.runtime_db import create_task
import asyncio

# interval 类型（每 5000ms 触发）
task = asyncio.run(create_task(
    paths,
    role="general_office",
    task="定时任务内容",
    schedule_type="interval",
    schedule_value="5000",        # 毫秒
    next_run_at="2026-03-23T08:00:00Z",
))

# cron 类型
task = asyncio.run(create_task(
    paths,
    role="general_office",
    task="每天凌晨运行",
    schedule_type="cron",
    schedule_value="0 0 * * *",
    next_run_at="2026-03-24T00:00:00Z",
))
```

### 运行测试

```bash
python3 -m unittest discover -s tests -q
```
