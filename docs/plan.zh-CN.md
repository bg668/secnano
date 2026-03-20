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
