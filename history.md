# 历史记录

## 2026-03-20

### Subagent Runtime：Milestone C — P0 执行层（已完成）

已完成功能：

1. `secnano/runtime_db.py` 补全执行层函数：`claim_task`（原子 UPDATE）、`mark_running`、`mark_done`、`mark_failed`、`append_run_log`、`list_pending_tasks`、`update_task_status`；新增 `task_run_logs` 建表 SQL 与唯一索引；新增 `TASK_ACTIVE_STATUSES`。
2. 新增 `secnano/worker_pool.py`：`WorkerPool` 常驻管理器，支持 `start/stop/status/enqueue`，后台调度线程每 5s 扫描 pending tasks 并 `try_spawn`，子进程超时后 `proc.kill()` 并 `mark_failed`。
3. 新增 `secnano/agent_loop.py`：`run_agent_loop()` 标准 agent loop 骨架，支持工具调用与多轮对话。
4. 新增 `secnano/llm_client.py`：轻量 Anthropic LLM 客户端，通过 `ANTHROPIC_API_KEY`/`ANTHROPIC_AUTH_TOKEN`/`ANTHROPIC_BASE_URL`/`SECNANO_MODEL` 环境变量配置。
5. 新增 `secnano/tools/__init__.py` 与 `secnano/tools/dispatch.py`：`TOOL_HANDLERS` dispatch map（`read_file/write_file/edit_file/run_command`）、`safe_path` 沙箱、`TOOL_SCHEMAS` anthropic 格式工具定义。
6. 新增 `secnano/subagent/__init__.py` 与 `secnano/subagent/subagent_entry.py`：子进程入口，解码 base64 任务 JSON → 构建 system prompt → 调用 `run_agent_loop` → `mark_done/mark_failed`。
7. 新增 `secnano/_subagent.py`：`python3 -m secnano._subagent <base64_task_json>` 入口。
8. `secnano/__main__.py` 补充 `workers start/status/stop` CLI 子命令；`workers start` 以前台常驻方式运行 WorkerPool，每秒处理 IPC 文件并扫描 pending tasks。
9. `pyproject.toml` 追加 `anthropic>=0.40.0` 依赖。
10. 新增测试 `tests/test_worker_pool.py`，覆盖 `claim_task` 原子性、`mark_done` 状态、`mark_failed` 状态、`list_pending_tasks` 过滤、`append_run_log`、`update_task_status`。
11. 新增开发计划文档 `docs/plan.zh-CN.md`（里程碑总览 + P0-P3 待办清单 + 验收标准）。

验收命令（已通过）：

1. `python3 -m unittest discover -s tests -q`
2. `python3 -m secnano workers --help`
3. `python3 -m secnano workers status`

## 2026-03-19

### Subagent Runtime：Milestone A 开发启动（进行中）

已完成功能：

1. 新增 `secnano` 包基础入口，支持 `python3 -m secnano` 与 `--version`。
2. 新增运行时路径模型 `ProjectPaths`，统一 `runtime/db/secnano.sqlite3` 的绝对路径发现与目录初始化。
3. 新增 SQLite 任务存储最小实现（`tasks` 表、WAL、`busy_timeout`）。
4. 新增 `tasks submit`：可创建 `pending` 任务并返回任务详情（支持 `--json`）。
5. 新增 `tasks show` / `tasks list`：支持按 `task_id` 查询与按状态列表查询（支持 `--json`）。
6. 新增 `tasks poll`：支持按超时轮询任务状态，未到终态时超时返回 `124`。
7. 新增最小测试集 `tests/test_tasks_cli.py`，覆盖 submit/show、list 状态过滤、poll 超时返回码。

验收命令（已通过）：

1. `python3 -m unittest tests.test_tasks_cli -q`
2. `python3 -m unittest discover -s tests -q`
3. `python3 -m secnano --help`
4. `python3 -m secnano tasks submit --role general_office --task "手工验证 submit" --json`
5. `python3 -m secnano tasks list --status pending --limit 5 --json`

## 2026-03-20

### Subagent Runtime：Milestone B（IPC 对齐，已完成）

已完成功能：

1. 新增 IPC 路径支持：`runtime/ipc/<namespace>/{tasks,results}` 与 `runtime/ipc/errors`。
2. 新增 `ipc_writer`：支持构造 v1 task 请求并采用 `*.tmp -> rename` 原子写入任务文件。
3. 新增 `ipc_watcher`：支持扫描 `tasks/*.json` 并将合法请求入库到 SQLite。
4. 新增 namespace 授权模块（当前最小策略：仅允许 `main`）。
5. 新增错误归档：坏 JSON、无权限 namespace、无效 payload 均写入 `runtime/ipc/errors/*.json`。
6. 新增 `ipc write-task` CLI：支持 `--file /abs/path/*.json` 或命令行参数构造任务。
7. 新增 `ipc watch` CLI：支持按 namespace 处理 IPC 任务文件并输出处理结果。
8. 对 watcher 加入处理后清理策略：成功与失败均删除已处理任务文件，避免重复扫描。
9. 新增测试 `tests/test_ipc_cli.py`，覆盖“写入并触发执行”与“越权拒绝并归档错误”。

验收命令（已通过）：

1. `python3 -m unittest tests.test_ipc_cli -q`
2. `python3 -m unittest discover -s tests -q`
3. `python3 -m secnano ipc write-task --role general_office --task "B 手工验证" --namespace main --json`
4. `python3 -m secnano ipc watch --namespace main --json`
5. `python3 -m secnano tasks list --status pending --limit 5 --json`

## 2026-03-17

### Milestone 0：工程骨架（已完成）

已完成功能：

1. 新增 `secnano` 独立 Python 包结构，支持 `python3 -m secnano` 运行。
2. 新增独立 CLI 入口，支持命令分发与 `--version`。
3. 新增 `doctor` 命令，提供本地环境检查（Python 版本、`refs` 路径、`.venv`、`nanobot` runtime bridge）。
4. 新增 `bootstrap` 命令，支持 `--dry-run` 预演初始化步骤（虚拟环境、editable 安装）。
5. 新增 `secnano` 的 `nanobot` runtime bridge 检查入口（`runtime_bridge` 模块）。
6. 补充根目录 `README.md` 与 `pyproject.toml` 构建配置，修复 `pip install -e .` 可执行链路。

验收命令（已通过）：

1. `python3 -m secnano --help`
2. `python3 -m secnano doctor`
3. `python3 -m secnano bootstrap --dry-run`
4. `.venv/bin/python -m pip install -e .`

备注：

- 当前环境无 `python` 命令别名，请使用 `python3` 或 `.venv/bin/python`。

### 兼容层路径治理与进展看板（已完成）

已完成功能：

1. 将上游兼容依赖从 `refs/nanobot/` 迁移到 `packages/nanobot/`。
2. 更新 `secnano` 路径上下文，新增 `packages_dir` 并统一用于兼容层路径解析。
3. 更新 `doctor` 检查项，改为检查 `packages/nanobot`，并更新提示文案。
4. 更新 `bootstrap` 安装步骤，改为安装 `packages/nanobot` editable 依赖。
5. 更新 runtime bridge 元数据字段，改为输出 `package_location`。
6. 更新模块边界文档中的目录结构示意，明确 `packages/nanobot` 与 `refs/{pyclaw,nanoclaw}` 分层。
7. 重构 `project_progress.md`，按核心业务模块与基础支撑模块展示完成看板，便于总览开发进度。

验收命令（已通过）：

1. `.venv/bin/python -m secnano doctor`
2. `.venv/bin/python -m secnano bootstrap --dry-run`
3. `.venv/bin/python -m secnano bootstrap`

### Milestone 1：单一主控 agent 与安全委派最小链路（已完成）

已完成功能：

1. 新增任务模型：`DelegateRequest`、`DelegateResult`、`TaskArchiveRecord`。
2. 新增角色资产模块：支持 `roles ensure-defaults` 与 `roles list`。
3. 新增后端协议 `SubagentBackend` 与 `host` backend 最小实现。
4. 新增委派命令 `delegate`：支持后端选择、角色校验、执行与归档。
5. 新增审计命令 `audit list`：支持读取 `runtime/tasks/*.json` 归档。
6. 新增调试日志能力：`roles/delegate/audit` 支持 `--debug`。

验收命令（已通过）：

1. `.venv/bin/python -m secnano roles ensure-defaults`
2. `.venv/bin/python -m secnano roles list`
3. `.venv/bin/python -m secnano delegate --backend host --role general_office --task "完成模块化开发最小链路" --json`
4. `.venv/bin/python -m secnano audit list --json`
5. `.venv/bin/python -m secnano delegate --backend host --role general_office --task "调试日志验证" --debug`

### Milestone 2：容器后端接入准备（validated 阶段，已完成）

已完成功能：

1. 新增 `runtime inspect` 命令，输出 `docker/node/npm/refs/packages` 依赖明细。
2. 新增 `runtime validate` 命令，支持 required/optional 校验与退出码。
3. 新增 `pyclaw_container` backend，支持 validated 阶段执行返回。
4. 更新 `delegate` 命令，支持 `--backend pyclaw_container` 并写入归档。
5. 将运行时校验逻辑抽象为 `runtime_checks` 模块，便于后续复用与调试。

验收命令（已通过）：

1. `.venv/bin/python -m secnano runtime inspect --json`
2. `.venv/bin/python -m secnano runtime validate --json`
3. `.venv/bin/python -m secnano delegate --backend pyclaw_container --role general_office --task "容器后端准备链路验收" --json`
4. `.venv/bin/python -m secnano audit list --limit 5 --json`

### Milestone 3：角色治理最小闭环（已完成）

已完成功能：

1. 新增 `roles show` 命令：读取角色 `SOUL/ROLE/MEMORY/POLICY` 与 `skills`。
2. 新增 `audit show` 命令：按 `task_id` 读取单任务归档。
3. 新增 `roles promote-memory` 命令：将任务摘要提升写入角色 `MEMORY.md`。
4. 归档存储新增 `get_record(task_id)` 单条读取能力。
5. memory promotion 新增幂等保护：同一 `task_id` 不重复写入。

验收命令（已通过）：

1. `.venv/bin/python -m secnano roles show general_office --json`
2. `.venv/bin/python -m secnano audit show 406b3988f660 --json`
3. `.venv/bin/python -m secnano roles promote-memory general_office 406b3988f660 --json`
4. `.venv/bin/python -m secnano roles promote-memory general_office 406b3988f660 --json`（重复执行返回 `already_promoted`）

### Milestone 4：能力适配接口（已完成，最小闭环）

已完成功能：

1. 新增 `CapabilityAdapter` 合同与 `CapabilitySpec/AdapterSnapshot` 数据结构。
2. 新增内置适配器：`host_execution`、`pyclaw_container`、`nanobot_runtime`。
3. 新增适配器注册表，统一输出适配器可用性与能力快照。
4. 新增 `adapters list` 命令，支持文本与 JSON 输出。
5. 新增 `tools` 命令，输出工具目录、来源适配器与能力映射。

验收命令（已通过）：

1. `.venv/bin/python -m secnano adapters list`
2. `.venv/bin/python -m secnano adapters list --json`
3. `.venv/bin/python -m secnano tools`
4. `.venv/bin/python -m secnano tools --json`
5. `.venv/bin/python -m secnano doctor --json`
