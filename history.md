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
