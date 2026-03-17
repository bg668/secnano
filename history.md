# 历史记录

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
