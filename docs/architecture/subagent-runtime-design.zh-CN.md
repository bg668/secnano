# SecNano 子进程任务编排最终架构设计（aiosqlite + 文件 IPC + nanoclaw Queue 对齐）

> 状态：Design Draft（可直接作为实现与拆任务依据）  
> 适用范围：`secnano` 主工程（不修改 `refs/*` 参考实现）

## 1. 文档目录结构（建议直接落库）

建议在仓库中采用如下文档结构，便于后续持续演进：

```text
docs/
  architecture/
    subagent-runtime-design.zh-CN.md      # 本文：最终架构与开发方案
    subagent-runtime-adr.zh-CN.md         # 可选：关键取舍 ADR（是否子进程直写 DB 等）
  protocols/
    ipc-task-protocol.v1.json             # 可选：IPC 协议样例
    ipc-result-protocol.v1.json           # 可选：结果协议样例
```

当前先落地一份主设计文档（本文），后续可按里程碑将协议样例拆成独立文件。

---

## 2. 目标与边界

### 2.1 目标

1. 子任务执行统一采用**子进程**模型。
2. 任务与结果以 **SQLite（aiosqlite）** 持久化为准。
3. 主-子消息通道采用**文件 IPC**（轮询 watcher）。
4. 并发控制遵循 nanoclaw 的 GroupQueue 思想：
   - 有空闲 worker 立即执行
   - 无空闲则入队等待
   - worker 释放后持续 drain waiting 队列
5. 主 Agent 通过 `poll(task_id)` 轮询获取任务结果。
6. 记忆能力抽象为统一 tool，主/子可共享调用。

### 2.2 非目标（MVP 阶段）

1. 不在 MVP 引入分布式消息中间件。
2. 不在 MVP 引入复杂多级优先级调度。
3. 不在 MVP 引入外部向量库（记忆先以 SQLite 为主）。

---

## 3. 系统总览（最终形态）

### 3.1 组件

1. **Main Agent（Python / nanobot-based）**
   - 创建任务、入库、投递、轮询结果。
2. **WorkerPool 常驻管理器**
   - 维护 `MAX_WORKERS`、排队、回收、重试与超时处理。
3. **SubAgent 子进程**
   - 接收任务（stdin JSON），执行工具链，回写 DB。
4. **IPC 层（文件）**
   - `tasks/*.json`、`results/*.json`、`errors/`。
5. **SQLite（aiosqlite）**
   - 任务状态机、执行日志、幂等约束。
6. **Memory Tool**
   - 主/子共享接口与存储。

### 3.2 关键执行链路

1. 主 Agent 创建任务：`pending`。
2. Scheduler/Watcher 发现待执行任务，交给 WorkerPool。
3. WorkerPool 依据 `MAX_WORKERS` 决策：
   - 可执行：`spawn_subagent()`
   - 否则入等待队列
4. 子进程执行并回写：
   - `done` + `result`
   - 或 `failed` + `error`
5. 主 Agent `poll(task_id)` 轮询 DB 直至终态。

---

## 4. 模块分层与接口草案

## 4.1 `db/`（aiosqlite）

| 接口 | 说明 | 关键约束 |
|---|---|---|
| `init_db()` | 初始化 schema / pragma | `journal_mode=WAL`，`busy_timeout` |
| `create_task(...)` | 创建任务记录 | `task_id` 幂等唯一 |
| `get_task(task_id)` | 查询单任务 | 返回状态/结果/错误 |
| `list_pending_tasks(limit)` | 拉取待执行任务 | 按 `created_at` 递增 |
| `claim_task(task_id, worker_id)` | 原子领取任务 | `UPDATE ... WHERE status IN ('pending','queued')` |
| `mark_done(task_id, result)` | 标记成功 | 写 `finished_at` |
| `mark_failed(task_id, error)` | 标记失败 | 写 `finished_at` |
| `append_run_log(...)` | 追加执行日志 | 保留每次尝试信息 |

---

## 4.2 `ipc/`（文件通信）

| 模块 | 说明 |
|---|---|
| `ipc_writer.py` | 写 `tasks/messages/results` 文件（tmp + rename） |
| `ipc_watcher.py` | 轮询目录，解析请求并分发到 DB/WorkerPool |
| `ipc_auth.py` | namespace 授权校验（main 与非 main） |

---

## 4.3 `worker_pool/`（并发控制）

| 接口 | 说明 |
|---|---|
| `enqueue_task(task_id, payload)` | 入等待队列 |
| `try_spawn(task)` | `active < MAX_WORKERS` 时立即启动 |
| `drain_waiting()` | worker 释放后持续拉起 |
| `spawn_subagent(task)` | `subprocess.Popen` 启动并附带超时控制 |
| `on_worker_exit(...)` | 处理结果、失败、重试与资源回收 |

---

## 4.4 `subagent/`

| 接口 | 说明 |
|---|---|
| `subagent_entry.py` | stdin 读取任务 JSON，执行后回写 DB |
| `execute_task(...)` | 调用 nanobot runtime + tools（含 memory tool） |

---

## 4.5 `tools/memory_tool.py`

| 接口 | 说明 |
|---|---|
| `store(key, value, meta)` | 写入记忆 |
| `retrieve(query, top_k)` | 检索记忆 |
| `promote(task_id, summary)` | 任务归档后的记忆提升（幂等） |

---

## 5. SQL Schema 草案（SQLite）

> 说明：字段覆盖最小可运行链路 + nanoclaw 风格状态机。

```sql
PRAGMA journal_mode=WAL;
PRAGMA busy_timeout=5000;

CREATE TABLE IF NOT EXISTS tasks (
  task_id TEXT PRIMARY KEY,
  namespace TEXT NOT NULL DEFAULT 'main',
  role TEXT,
  status TEXT NOT NULL,              -- pending/queued/running/done/failed/paused/cancelled
  payload_json TEXT NOT NULL,
  result_json TEXT,
  error_text TEXT,
  worker_id TEXT,
  retry_count INTEGER NOT NULL DEFAULT 0,
  max_retries INTEGER NOT NULL DEFAULT 0,
  created_at TEXT NOT NULL,
  updated_at TEXT NOT NULL,
  started_at TEXT,
  finished_at TEXT,
  next_run_at TEXT
);

CREATE INDEX IF NOT EXISTS idx_tasks_status_created
ON tasks(status, created_at);

CREATE INDEX IF NOT EXISTS idx_tasks_next_run
ON tasks(next_run_at);

CREATE TABLE IF NOT EXISTS task_run_logs (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  task_id TEXT NOT NULL,
  attempt_no INTEGER NOT NULL,
  worker_id TEXT,
  status TEXT NOT NULL,              -- running/done/failed/timeout/killed
  duration_ms INTEGER,
  error_text TEXT,
  result_json TEXT,
  created_at TEXT NOT NULL,
  FOREIGN KEY(task_id) REFERENCES tasks(task_id)
);

CREATE UNIQUE INDEX IF NOT EXISTS idx_task_run_logs_unique_attempt
ON task_run_logs(task_id, attempt_no);

CREATE TABLE IF NOT EXISTS memory_items (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  namespace TEXT NOT NULL DEFAULT 'main',
  role TEXT,
  key TEXT NOT NULL,
  value_json TEXT NOT NULL,
  source_task_id TEXT,
  promoted INTEGER NOT NULL DEFAULT 0,
  created_at TEXT NOT NULL
);
```

### 5.1 原子 claim 语义（示例）

```sql
UPDATE tasks
SET status='running',
    worker_id=?,
    started_at=?,
    updated_at=?
WHERE task_id=?
  AND status IN ('pending', 'queued');
```

应用层以 `rowcount == 1` 视为领取成功，防止双领。

---

## 6. IPC JSON 协议草案（v1）

## 6.1 主 -> 系统（tasks）

路径：`runtime/ipc/<namespace>/tasks/<task_id>.json`

```json
{
  "version": "v1",
  "request_id": "req_01J...",
  "task_id": "task_01J...",
  "namespace": "main",
  "role": "general_office",
  "created_at": "2026-03-19T13:00:00Z",
  "payload": {
    "task": "生成每日风险摘要",
    "context": {
      "source": "cli"
    }
  },
  "options": {
    "timeout_sec": 120,
    "max_retries": 1,
    "idempotency_key": "task_01J..."
  }
}
```

## 6.2 子 -> 系统（results，可选）

路径：`runtime/ipc/<namespace>/results/<task_id>.json`

```json
{
  "version": "v1",
  "task_id": "task_01J...",
  "worker_id": "worker_02",
  "status": "done",
  "finished_at": "2026-03-19T13:00:08Z",
  "result": {
    "summary": "任务执行成功",
    "artifacts": []
  },
  "error": null
}
```

## 6.3 错误归档（errors）

路径：`runtime/ipc/errors/<timestamp>_<name>.json`

```json
{
  "version": "v1",
  "source_path": "runtime/ipc/dev/tasks/task_bad.json",
  "namespace": "dev",
  "error_code": "IPC_AUTH_DENIED",
  "error_message": "namespace dev is not allowed to submit privileged task",
  "created_at": "2026-03-19T13:00:10Z"
}
```

---

## 7. 状态机与轮询策略

## 7.1 状态机（建议）

- `pending`：已创建，待调度  
- `queued`：已入等待队列  
- `running`：子进程执行中  
- `done`：成功完成  
- `failed`：执行失败  
- `paused` / `cancelled`：可选扩展态

## 7.2 轮询参数（建议）

- `IPC_POLL_INTERVAL_MS=1000`
- `TASK_POLL_INTERVAL_MS=1000`
- `SCHEDULER_SCAN_INTERVAL_MS=5000`

---

## 8. CLI 命令草案（沿用当前习惯：`python3 -m secnano ...`）

> 目标：与现有命令风格统一；命令名可在实现阶段微调。

| 命令 | 说明 |
|---|---|
| `python3 -m secnano tasks submit --role general_office --task "..." --json` | 提交任务并返回 `task_id` |
| `python3 -m secnano tasks poll <task_id> --timeout 120 --json` | 轮询任务结果 |
| `python3 -m secnano tasks show <task_id> --json` | 查看任务详情与状态 |
| `python3 -m secnano tasks list --status pending --limit 20 --json` | 列表查询 |
| `python3 -m secnano workers start --max-workers 4` | 启动 worker 常驻进程 |
| `python3 -m secnano workers status --json` | 查看 active/waiting/容量 |
| `python3 -m secnano workers stop` | 停止 worker 常驻进程 |
| `python3 -m secnano ipc watch --namespace main` | 启动 IPC watcher |
| `python3 -m secnano ipc write-task --file /abs/path/task.json` | 手工投递 IPC 任务文件 |
| `python3 -m secnano memory store --role general_office --key k --value-json '{}'` | 写记忆 |
| `python3 -m secnano memory retrieve --role general_office --query "..." --json` | 读记忆 |
| `python3 -m secnano memory promote --role general_office --task-id <task_id> --json` | 提升任务记忆（幂等） |

---

## 9. 里程碑交付与验收

## Milestone A（MVP）

**交付**
1. DB schema + aiosqlite + 原子 claim
2. WorkerPool（`MAX_WORKERS` + waiting + drain）
3. subagent 子进程执行链路
4. `tasks submit/poll` CLI 最小闭环

**验收**
1. 单任务执行：`pending -> running -> done`
2. 并发上限验证：`MAX_WORKERS=2` 时 10 任务峰值仅 2 个 running
3. 崩溃回写：kill 子进程后标记 `failed`（或按策略重试）

## Milestone B（IPC 对齐）

**交付**
1. IPC writer + watcher + errors 归档
2. namespace 授权

**验收**
1. 写 tasks 文件可触发执行
2. 越权请求被拒绝并落 errors

## Milestone C（稳定性）

**交付**
1. WAL / busy_timeout / 重试策略
2. 超时 kill 与失败归档
3. 幂等投递（同 task_id 不重复执行）

**验收**
1. 100 任务压测无数据错乱
2. 重复投递行为符合预期

## Milestone D（记忆工具）

**交付**
1. 统一 Memory Tool
2. 主/子共享读写
3. promote-memory 与任务归档绑定

**验收**
1. 子写主读成功
2. 同 task_id 提升幂等

---

## 10. 实施注意事项（工程约束）

1. 所有路径使用绝对路径（与现有工程约束一致）。
2. IPC 文件写入采用“`*.tmp` -> `rename`”避免半写文件。
3. 子进程 stdout/stderr 需归档到 run_log，便于排障。
4. 不以结果文件作为最终真相源，**统一以 SQLite 状态为准**。
5. 所有状态迁移必须经过受控函数，禁止散落 SQL 直接改状态。

