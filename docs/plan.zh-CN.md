# secnano 开发计划（中文版）

> 最后更新：2026-03-20

---

## 一、里程碑完成状态总览

| 里程碑 | 名称 | 状态 | 核心模块 |
|--------|------|------|---------|
| Milestone A | Tasks CRUD（任务增删改查）| ✅ 已完成 | `runtime_db.py`、`__main__.py tasks` |
| Milestone B | IPC 文件投递（任务文件写入与扫描）| ✅ 已完成 | `ipc_writer.py`、`ipc_watcher.py`、`ipc_auth.py` |
| Milestone C | P0 执行层（打通最小可跑链路）| ✅ 已完成 | `worker_pool.py`、`agent_loop.py`、`llm_client.py`、`tools/dispatch.py`、`subagent/` |
| Milestone D | P1 单 agent 可靠性 | ⏳ 待开发 | `context_compact.py`、`skill_loader.py`、`tools/memory_tool.py` |
| Milestone E | P2 多 agent 协作 | ⏳ 待开发 | `team/teammate_manager.py`、`team/message_bus.py`、`team/protocols.py` |
| Milestone F | P3 并行隔离执行 | ⏳ 待开发 | `worktree_manager.py`、`autonomous_loop.py` |

---

## 二、待办清单（按优先级）

### P0 — 打通最小可跑链路（Milestone C）✅

> 目标：使一个任务能完整走完 `pending → running → done` 链路。

- [x] `secnano/runtime_db.py` 补全 `claim_task`、`mark_running`、`mark_done`、`mark_failed`、`append_run_log`、`list_pending_tasks`、`update_task_status`；新增 `task_run_logs` 表
- [x] 新建 `secnano/worker_pool.py`：`WorkerPool` 常驻管理器（`start/stop/status/enqueue/_scheduler_loop/_try_spawn/_spawn_worker/_on_worker_exit`）
- [x] 新建 `secnano/agent_loop.py`：`run_agent_loop()` while-True 工具调用骨架
- [x] 新建 `secnano/llm_client.py`：轻量 Anthropic LLM 客户端（环境变量配置）
- [x] 新建 `secnano/tools/dispatch.py`：`TOOL_HANDLERS` dispatch map + `safe_path` + 输出截断
- [x] 新建 `secnano/subagent/subagent_entry.py`：子进程入口（解码任务 → 执行 → 回写 DB）
- [x] 新建 `secnano/_subagent.py`：`python3 -m secnano._subagent` 入口
- [x] `secnano/__main__.py` 补充 `workers start/status/stop` 子命令
- [x] `pyproject.toml` 追加 `anthropic>=0.40.0` 依赖
- [x] 新建 `tests/test_worker_pool.py`：覆盖 `claim_task` 原子性、`mark_done`、`mark_failed`、`list_pending_tasks`

**P0 验收标准：**
```bash
# 所有测试通过
python3 -m unittest discover -s tests -q

# 启动 WorkerPool（配置 ANTHROPIC_API_KEY 后）
python3 -m secnano workers start --max-workers 2

# 提交任务
python3 -m secnano tasks submit --role general_office --task "写一首关于 agent 的俳句" --json

# 轮询结果
python3 -m secnano tasks poll <task_id> --timeout 60 --json

# 查看任务详情（期望 status=done, result 中有 summary）
python3 -m secnano tasks show <task_id> --json
```

---

### P1 — 单 agent 可靠性（Milestone D）⏳

> 目标：agent 在长任务、大上下文场景下仍然可靠完成。

- [ ] 新建 `secnano/context_compact.py`：
  - `micro_compact(messages)`：老 tool_result 替换为短占位符
  - `auto_compact(messages, paths)`：token 超阈值 → 保存 transcript → LLM 摘要 → 重置 messages
  - JSONL transcript 落盘到 `.transcripts/`
- [ ] 新建 `secnano/subagent/runner.py`：`run_subagent(prompt, paths)` 独立 loop + 摘要回传
- [ ] 新建 `roles/*/skills/` 目录结构 + `SKILL.md`（YAML frontmatter + 正文）
- [ ] 新建 `secnano/skill_loader.py`：`SkillLoader`（`rglob` 扫描 + `catalog` + `load_skill` handler）
- [ ] 新建 `secnano/tools/memory_tool.py`：`store/retrieve/promote` 工具
- [ ] `secnano/runtime_db.py` 补 `memory_items` 建表

**P1 验收标准：**
- 长任务（>30 轮工具调用）不崩溃
- 上下文超阈值时自动压缩并继续执行
- 技能按需加载：`load_skill("git-workflow")` 在 tool_result 中注入技能内容
- memory 工具可写入、读取、提升记忆条目

---

### P2 — 多 agent 协作（Milestone E）⏳

> 目标：多个 agent 能分工协作、异步通信、协商关机。

- [ ] 新建 `secnano/team/teammate_manager.py`：`spawn`、状态管理、线程生命周期
- [ ] 新建 `secnano/team/message_bus.py`：JSONL inbox（`send()` append-only；`read_inbox()` drain）
- [ ] 新建 `secnano/team/protocols.py`：request-response FSM（`pending → approved | rejected`）
- [ ] 新建 `secnano/todo_manager.py`：TodoManager + nag reminder 注入（连续 3 轮未更新则注入提醒）

**P2 验收标准：**
- 可启动 coder + reviewer 两个 teammate，互发消息并收到回复
- 协商关机：shutdown_request → shutdown_response 完整链路
- nag reminder 在任务停滞时注入到 tool_results

---

### P3 — 并行隔离执行（Milestone F）⏳

> 目标：多个 agent 并行执行，各自使用独立的 git worktree 目录。

- [ ] 新建 `secnano/worktree_manager.py`：
  - `create(name)` → `git worktree add`
  - `bind(task_id, name)` → 绑定任务与 worktree，推进状态到 in_progress
  - `remove(name, complete_task=False)` → worktree 清理 + 可选同步完成任务
  - `index.json` 注册表 + `events.jsonl` 生命周期事件
- [ ] 新建 `secnano/autonomous_loop.py`：
  - WORK/IDLE 双阶段循环
  - `scan_unclaimed_tasks()` → 自动认领未分配任务
  - idle timeout（60s 无事 → shutdown）
  - 上下文压缩后身份重注入（`<identity>...</identity>`）

**P3 验收标准：**
- 3 个 agent 并行运行，各自占据独立 worktree 目录
- 任务完成后 worktree 自动清理
- 多 agent 并发 claim 无竞争条件（原子 claim_task）

---

## 三、关键约束

1. **所有路径使用绝对路径**（与 `ProjectPaths` 已有约束一致）
2. **不破坏现有接口**：`runtime_db.py` 现有函数签名保持不变，只新增
3. **测试必须通过**：`python3 -m unittest discover -s tests -q`
4. **子进程通信**：任务 JSON 通过 base64 argv 传递（避免引号转义问题），`db_path` 也包含在任务 JSON 中
5. **错误处理**：子进程崩溃/超时都必须 `mark_failed`，不能让任务永远停在 `running`
6. **无 API key 时**：`workers start` 能启动，但子 agent 执行时会 `mark_failed` 并给出清晰错误（不崩溃 WorkerPool）

---

## 四、模块依赖关系图

```
__main__.py
  ├── runtime_db.py          (tasks CRUD + execution state)
  ├── worker_pool.py         (subprocess management)
  │     └── subagent/_subagent.py  (subprocess entry)
  │           ├── agent_loop.py    (LLM loop)
  │           │     └── llm_client.py  (Anthropic SDK)
  │           └── tools/dispatch.py  (tool handlers)
  ├── ipc_watcher.py         (file-based task ingestion)
  └── paths.py               (ProjectPaths)
```

---

## 五、参考资料

- Agent Loop 模式（S01）：`while True` + `tool_use/tool_result` 闭环
- Tool Dispatch（S02）：dispatch map + `safe_path` 沙箱 + 输出截断
- Context Compact（S06）：micro_compact + auto_compact + transcripts
- Task System（S07）：磁盘持久化任务图（DAG）
- Background Tasks（S08）：后台线程 + drain-on-turn
- Agent Teams（S09）：JSONL inbox + 异步通信
- Autonomous Agents（S11）：WORK/IDLE 双阶段 + auto-claim
- Worktree Isolation（S12）：git worktree + 任务绑定

---

## 六、主控优先路线（Phase 1 & Phase 2）

> 最后更新：2026-03-23
>
> 策略：优先跑通任务管理、调度、资源分配（主控侧），再增强 subagent 执行侧。
> 在现有代码基础上增量叠加，不推翻已有架构。

### 里程碑总览

| Task | 名称 | 阶段 | 状态 | 核心文件 |
|------|------|------|------|---------|
| Task 1 | DB 层升级：aiosqlite + 调度字段 | Phase 1 | ⏳ 待开发 | `runtime_db.py` |
| Task 2 | 调度引擎：Scheduler（cron/interval/once） | Phase 1 | ⏳ 待开发 | `scheduler.py` |
| Task 3 | WorkerPool 完善：超时状态、run_log、健壮性 | Phase 1 | ⏳ 待开发 | `worker_pool.py` |
| Task 4 | CLI 扩展：pause / resume / cancel / retry | Phase 1 | ⏳ 待开发 | `__main__.py` |
| Task 5 | IPC Watcher 独立化 + 主控 Daemon 整合 | Phase 1 | ⏳ 待开发 | `ipc_watcher.py`、`__main__.py` |
| Task 6 | 端到端集成测试 + 文档 | Phase 1 | ⏳ 待开发 | `tests/`、`README.md` |
| Task 7 | MemoryTool 抽象 + Mem0 实现 | Phase 2 | ⏳ 待开发 | `tools/memory.py` |
| Task 8 | 工具系统增强：环境变量策略、审计、安全 | Phase 2 | ⏳ 待开发 | `tools/dispatch.py`、`tools/audit.py` |
| Task 9 | Subagent 角色系统完善 + 多角色测试 | Phase 2 | ⏳ 待开发 | `subagent/subagent_entry.py`、`roles/` |

---

### Phase 1：主控侧（Orchestrator）

#### Task 1 — DB 层升级：aiosqlite + 调度字段

**目标**：将 DB 层从同步 `sqlite3` 迁移到 `aiosqlite`，同时补全定时任务所需字段。

**涉及文件**：
- `secnano/runtime_db.py` → 全部改写为 async（`aiosqlite`）
- Schema 新增字段：`schedule_type TEXT`（cron/interval/once/null）、`schedule_value TEXT`、`last_run TEXT`、`last_result_json TEXT`
- 新增/修改 `status` 枚举：加入 `timeout`、`paused`（原有 cancelled 保留）
- 所有现有函数改为 `async def`
- 新增 `mark_timeout(task_id, error_detail: dict)`（记录 pid、duration、last_output）
- 新增 `get_due_tasks(now: datetime) -> list[TaskRecord]`
- 新增 `update_schedule_after_run(task_id, next_run)`
- 新增 `mark_paused / mark_resumed / mark_cancelled`
- CLI 查询路径（`__main__.py`）改用 `asyncio.run()` 包裹
- `pyproject.toml` 加入 `aiosqlite` 依赖

**验收**：DB 的增删改查、claim 原子性、due_tasks 逻辑均可通过测试。

---

#### Task 2 — 调度引擎：Scheduler（cron/interval/once）

**目标**：实现定时任务引擎，独立于 WorkerPool，负责按时触发任务写入 pending。

**涉及文件**：
- 新增 `secnano/scheduler.py`
  - `class Scheduler`：持续轮询 `get_due_tasks(now)`，对到期任务调用 `update_schedule_after_run` 并将任务重新写入 pending（`create_task_with_id` 新 task_id，once 类型完成后置 completed）
  - 支持 cron 解析（依赖 `croniter` 库）、interval（毫秒）、once（时间戳）
  - 轮询间隔可配置（默认 10s）
- `pyproject.toml` 加入 `croniter` 依赖

**验收**：手动创建一个 interval=5s 的定时任务，观察 Scheduler 每 5s 自动产生新 pending task。

---

#### Task 3 — WorkerPool 完善：超时状态、run_log、并发健壮性

**目标**：补全超时处理语义，完善 run_log 记录，修复 attempt_no 硬编码问题。

**涉及文件**：
- `secnano/worker_pool.py`
  - 超时后调用 `mark_timeout` 而非 `mark_failed`，传入 `{pid, duration_ms, last_stderr}`
  - `_on_worker_exit` 中 attempt_no 改为从 DB 查当前 retry_count + 1
  - `WorkerPool.status()` 返回值补充实际运行中的 pid 映射

**验收**：提交一个会超时的任务，观察 DB 中状态为 `timeout`，run_log 有 pid 和 stderr 记录。

---

#### Task 4 — CLI 扩展：pause / resume / cancel / retry

**目标**：补全任务生命周期操作的 CLI 接口。

**涉及文件**：
- `secnano/__main__.py`
  - `tasks pause <task_id>`：调用 `mark_paused`
  - `tasks resume <task_id>`：调用 `mark_resumed`（重置为 pending）
  - `tasks cancel <task_id>`：调用 `mark_cancelled`
  - `tasks retry <task_id>`：读取原任务 payload，创建新 task_id 的 pending 任务（保留旧任务历史）
  - `tasks logs <task_id>`：打印 `task_run_logs` 中该任务所有记录

**验收**：可通过 CLI 完整执行 pause → resume → cancel → retry 流程，DB 状态变更正确。

---

#### Task 5 — IPC Watcher 独立化 + 集成进主循环

**目标**：将 IPC watcher 解耦为可独立启动的组件；确保主控 daemon 启动后 IPC + Scheduler + WorkerPool 三者协同运行。

**涉及文件**：
- `secnano/ipc_watcher.py`：提取出 `IPCWatcher` 类，支持 `start() / stop()`，内部维护自己的轮询线程
- `secnano/__main__.py`：`workers start` 命令改为统一启动 `IPCWatcher + Scheduler + WorkerPool` 三合一 daemon

**验收**：启动 daemon，通过 `ipc write-task` 写入任务文件，观察全链路自动流转：IPC 文件 → DB pending → WorkerPool spawn → DB done。

---

#### Task 6 — 端到端集成测试 + 文档

**目标**：跑通 Phase 1 完整链路，补充 README 和基础测试。

**涉及文件**：
- `tests/` 补充集成测试（至少覆盖：提交任务、poll 结果、定时任务触发、超时处理、retry）
- `README.md` 更新：架构说明、CLI 用法、配置项

**验收**：`pytest` 全部通过，README 可独立指导新人跑通主控链路。

---

### Phase 2：Subagent 增强

#### Task 7 — MemoryTool 抽象 + Mem0 实现

**目标**：为 subagent 提供可替换的记忆工具接口，默认实现用 Mem0。

**涉及文件**：
- 新增 `secnano/tools/memory.py`：定义 `MemoryTool` 抽象基类（`add / search / delete`），实现 `Mem0MemoryTool`
- `secnano/tools/dispatch.py`：注册 `memory_add / memory_search` 工具
- `pyproject.toml` 加入 `mem0ai` 可选依赖

**验收**：subagent 可调用 `memory_search` 查询历史记忆，结果写入 run_log。

---

#### Task 8 — 工具系统增强：环境变量策略、审计、安全

**目标**：工具调用规范化，补充审计日志。

**涉及文件**：
- `secnano/tools/dispatch.py`：`handle_run_command` 增加环境变量白名单、`cwd` 独立传参、输出截断策略可配置
- 新增 `secnano/tools/audit.py`：`append_audit_log(task_id, tool_name, input, output_summary)`，每次工具调用写入 `runtime/audit.jsonl`

**验收**：执行一次带工具调用的任务，`runtime/audit.jsonl` 中有完整记录。

---

#### Task 9 — Subagent 角色系统完善 + 多角色测试

**目标**：完善 role 加载逻辑，支持角色专属工具白名单。

**涉及文件**：
- `secnano/subagent/subagent_entry.py`：role 加载支持 `ROLE.md` + `TOOLS.json`（角色专属工具白名单）
- `roles/` 下补充 2-3 个示例角色（如 `code_reviewer`、`file_processor`）

**验收**：`general_office` 和 `code_reviewer` 两个角色分别执行任务，工具调用受角色白名单约束。

---

### 关键新增依赖

| 依赖 | 用途 | 引入于 |
|------|------|--------|
| `aiosqlite` | 异步 SQLite | Task 1 |
| `croniter` | cron 表达式解析 | Task 2 |
| `mem0ai` | 记忆工具（可选） | Task 7 |
