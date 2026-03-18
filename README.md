# secnano

`secnano` 是一个独立的 Python 包与 CLI 工具，目标是以“单一主控 agent + 安全委派”为核心，逐步落地文档中的里程碑能力。

当前已提供的可执行命令：

- `python3 -m secnano --help`
- `python3 -m secnano doctor`
- `python3 -m secnano bootstrap --dry-run`
- `python3 -m secnano roles ensure-defaults`
- `python3 -m secnano roles list`
- `python3 -m secnano roles show general_office`
- `python3 -m secnano roles promote-memory general_office <task-id>`
- `python3 -m secnano delegate --backend host --role general_office --task "..."`
- `python3 -m secnano audit list`
- `python3 -m secnano audit show <task-id>`
- `python3 -m secnano runtime inspect`
- `python3 -m secnano runtime validate`
- `python3 -m secnano delegate --backend pyclaw_container --role general_office --task "..."`
- `python3 -m secnano adapters list`
- `python3 -m secnano tools`

兼容阶段目录约定：

- `packages/nanobot/`：`nanobot` 上游兼容包
- `refs/pyclaw/`、`refs/nanoclaw/`：执行与安全机制参考实现

---

## 文档

### V2 架构文档（`architecture-v2` 分支）

| 文档 | 中文版 | 说明 |
|------|--------|------|
| [architecture_v2.md](docs/architecture_v2.md) | [architecture_v2_zh.md](docs/architecture_v2_zh.md) | V2 架构设计参考（模块定义、设计原则、朝廷隐喻） |
| [module_mapping_v2.md](docs/module_mapping_v2.md) | [module_mapping_v2_zh.md](docs/module_mapping_v2_zh.md) | 当前模块到 V2 模块的映射与操作分类 |
| [migration_plan_v2.md](docs/migration_plan_v2.md) | [migration_plan_v2_zh.md](docs/migration_plan_v2_zh.md) | V2 分阶段实施路线图（Phase 0–9） |

### 历史文档（`main` 分支）

| 文档 | 说明 |
|------|------|
| [docs/module_boundary_checklist.md](docs/module_boundary_checklist.md) | 原十二模块架构规范（历史参考） |
| [docs/development_milestones.md](docs/development_milestones.md) | M0–M4 里程碑与可执行交付物 |
| [docs/project_progress.md](docs/project_progress.md) | 当前各模块完成情况与下一步计划 |
| [docs/README.md](docs/README.md) | 文档目录导航 |
