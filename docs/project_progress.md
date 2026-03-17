# 项目进展

## 1. 文档目的

本文档用于提供“当前开发总览”，重点按核心模块展示完成情况，便于快速判断当前阶段与下一步优先级。

## 2. 当前仓库现状（2026-03-17）

当前仓库主要由以下部分组成：

1. `docs/`：模块边界、开发里程碑、项目进展导航文档。
2. `secnano/`：本项目自有实现代码（当前已落地 Milestone 0 可执行 CLI）。
3. `packages/nanobot/`：兼容阶段的上游运行时包（已从 `refs/nanobot/` 迁移）。
4. `refs/`：安全执行参考实现目录（当前保留 `refs/pyclaw/`、`refs/nanoclaw/`）。
5. `history.md`：已完成功能与阶段变更的时间线记录。

## 3. 核心模块完成看板

### 3.1 核心业务模块

| 模块 | 当前状态 | 完成情况 | 说明 |
|---|---|---|---|
| 输入输出模块 | 进行中 | 最小可用 | 已提供 `python3 -m secnano` CLI、`--help`、`doctor`、`bootstrap --dry-run`。 |
| 任务/消息模型模块 | 未开始 | 0% | 尚未定义统一 `Task/Reply/ExecutionRequest` 数据模型。 |
| 编排调度模块 | 未开始 | 0% | 尚未实现主控调度、角色选择、委派决策。 |
| 认知内核模块 | 兼容准备中 | 最小检查 | 当前仅有 `nanobot` runtime bridge 可用性检查，未接入实际 loop。 |
| 角色与能力资产模块 | 未开始 | 0% | 尚未落地角色资产加载、权限与策略读取。 |
| 执行模块 | 未开始 | 0% | 尚未落地 host/container 实际执行链路。 |
| 归档与状态模块 | 未开始 | 0% | 尚未落地任务归档、会话状态和审计查询。 |

### 3.2 基础支撑模块

| 模块 | 当前状态 | 完成情况 | 说明 |
|---|---|---|---|
| 配置管理模块 | 未开始 | 0% | 仅有项目上下文路径解析，未形成配置 schema/loader。 |
| AI 供应商模块 | 未开始 | 0% | 未建立 provider 合同与注册机制。 |
| 工具注册模块 | 未开始 | 0% | 未建立工具定义、权限与执行注册。 |
| 技能注册/加载模块 | 未开始 | 0% | 未建立技能扫描与加载流程。 |
| 能力适配模块 | 未开始 | 0% | 未定义 `CapabilityAdapter` 合同。 |

## 4. 已完成阶段性事项

### 4.1 Milestone 0：工程骨架（已完成）

1. 已创建 `secnano` 独立包与 CLI 入口。
2. 已落地 `doctor` 与 `bootstrap --dry-run`。
3. 已修复 `pip install -e .` 安装链路。

### 4.2 兼容层目录治理（已完成）

1. 已将 `nanobot` 从 `refs/nanobot/` 迁移到 `packages/nanobot/`。
2. 已同步更新 `doctor/bootstrap/runtime_bridge` 路径解析到 `packages/nanobot`。
3. 已同步更新相关文档中的目录声明与进展描述。

## 5. 下一步

下一阶段按 Milestone 1 落地“单一主控 agent 与安全委派最小链路”：

1. `python3 -m secnano roles ensure-defaults`
2. `python3 -m secnano roles list`
3. `python3 -m secnano delegate --backend host --role general_office --task "..."`
4. `python3 -m secnano audit list`
