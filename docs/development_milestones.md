# 开发里程碑

## 1. 文档目的

本文档把实施计划收敛为可执行里程碑。每个里程碑都必须以“可运行程序”作为交付标准，而不是只交付文档或空壳目录。

## 2. 里程碑总览

### Milestone 0：工程骨架

目标：

- 建立 `secnano` 独立包结构
- 建立独立 CLI 入口
- 建立 `nanobot` 运行时包装入口

可执行交付物：

- `python -m secnano --help`
- `python -m secnano doctor`
- `python -m secnano bootstrap --dry-run`

当前状态：

- 已完成

### Milestone 1：单一主控 agent 与安全委派最小链路

目标：

- 固定系统对外只有一个主控 agent 入口
- 建立 `SubagentBackend` 协议
- 建立 `host` backend
- 建立角色注册表
- 建立任务归档与审计读取
- 让委派链路可以通过 CLI 实际执行

可执行交付物：

- `python -m secnano roles ensure-defaults`
- `python -m secnano roles list`
- `python -m secnano delegate --backend host --role general_office --task "..." ...`
- `python -m secnano audit list`

当前状态：

- 已完成

已验证：

- 已通过 `.venv/bin/python -m secnano delegate --backend host --role general_office --task "..." --json` 返回真实 delegated 结果。

### Milestone 2：容器后端接入准备

目标：

- 建立 container adapter
- 建立 mount policy 和 secrets 采集
- 建立 `pyclaw_container` backend 的可执行准备链路

可执行交付物：

- `python -m secnano doctor --json`
- `python -m secnano runtime inspect`
- `python -m secnano runtime validate`
- `python -m secnano delegate --backend pyclaw_container --role general_office --task "..."`

当前状态：

- 已建立 validated 级链路，真实容器执行待完成

已验证：

- 已通过 `.venv/bin/python -m secnano runtime validate` 验证本地 `docker`、`node/npm` 与 `refs` 路径。
- 已通过 `.venv/bin/python -m secnano delegate --backend pyclaw_container --role general_office --task "..." --json` 返回 `validated` 状态。

### Milestone 3：角色治理最小闭环

目标：

- 建立角色资产包结构：`SOUL`、`MEMORY`、`skills`、`policy`
- 建立 role admin 读取接口
- 建立 memory promotion 最小实现
- 建立 audit 查看能力

可执行交付物：

- `python -m secnano roles show general_office`
- `python -m secnano audit show <task-id>`
- `python -m secnano roles promote-memory <role> <task-id>`

当前状态：

- 已具备 `ROLE/MEMORY` 最小读能力与 memory promotion 入口，`SOUL/policy` 尚未落地

### Milestone 4：能力适配接口

目标：

- 定义 `CapabilityAdapter` 合同
- 让外部新能力可以通过适配模块接入现有系统
- 保持系统只有一个主控 agent，而不是增加新的并行 agent
- 替换当前直接依赖上游私有装配逻辑的方式

可执行交付物：

- `python -m secnano adapters list`
- `python -m secnano doctor --json`
- `python -m secnano tools`

当前状态：

- 未开始，当前仅有 `nanobot` runtime bridge 的临时兼容层

## 3. 约束

1. 不直接修改 `nanobot` 源码。
2. 每新增一个可执行功能，都要同步更新 `history.md`。
3. 每完成一个里程碑节点，都要同步更新 [project_progress.md](/Users/biguncle/project/secnano/docs/project_progress.md)。
