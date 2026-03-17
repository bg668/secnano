# 项目进展

## 1. 文档目的

本文档用于提供“模块级总览”，重点展示每个核心模块的完成情况、可执行命令和下一步开发优先级。

## 2. 当前仓库现状（2026-03-17）

当前仓库主要由以下部分组成：

1. `secnano/`：本项目主实现代码（已落地 Milestone 0 ~ Milestone 3 最小链路）。
2. `roles/`：默认角色资产目录（当前已可自动生成 `general_office`）。
3. `runtime/tasks/`：任务归档目录（当前可写入并通过审计命令读取）。
4. `runtime` 命令：已支持 `inspect/validate` 运行时诊断。
5. `packages/nanobot/`：兼容阶段上游运行时包。
6. `refs/`：参考实现目录（`pyclaw`、`nanoclaw`）。
7. `docs/` + `history.md`：规划文档与功能时间线。

## 3. 核心模块完成看板

### 3.1 核心业务模块

| 模块 | 当前状态 | 完成情况 | 可执行/可调试能力 |
|---|---|---|---|
| 输入输出模块 | 已落地最小闭环 | 72% | CLI 已支持 `doctor/bootstrap/roles/delegate/audit/runtime/adapters/tools`，支持 `--json/--debug`。 |
| 任务/消息模型模块 | 已落地最小模型 | 40% | 已定义 `DelegateRequest/DelegateResult/TaskArchiveRecord`。 |
| 编排调度模块 | 已落地最小调度 | 50% | 已实现委派入口、backend 选择、角色校验、运行时校验联动与归档写入。 |
| 认知内核模块 | 兼容准备中 | 10% | 当前仅保留 `nanobot` runtime bridge 检查，未接入实际 loop。 |
| 角色与能力资产模块 | 已落地最小闭环 | 55% | 已支持 `roles show`、`roles promote-memory`，角色资产可读可写。 |
| 执行模块 | 已落地 host + container validated | 45% | 已有 `host` backend 与 `pyclaw_container` validated 链路。 |
| 归档与状态模块 | 已落地最小闭环 | 55% | 已支持 `audit list` 与 `audit show`，归档支持单条读取。 |

### 3.2 基础支撑模块

| 模块 | 当前状态 | 完成情况 | 说明 |
|---|---|---|---|
| 配置管理模块 | 进行中 | 40% | 已有 `ProjectContext`、运行时依赖校验与适配器可用性检查。 |
| AI 供应商模块 | 未开始 | 0% | 未定义 provider 合同与注册。 |
| 工具注册模块 | 已落地最小目录 | 30% | 已支持 `tools` 命令输出工具目录与来源适配器。 |
| 技能注册/加载模块 | 未开始 | 0% | 未定义技能扫描与加载机制。 |
| 能力适配模块 | 已落地最小闭环 | 55% | 已定义 `CapabilityAdapter` 合同、内置适配器与 `adapters list`。 |

## 4. 已完成阶段性事项

### 4.1 Milestone 0：工程骨架（已完成）

1. 建立独立包、CLI 入口、`doctor` 与 `bootstrap --dry-run`。
2. 建立 `nanobot` runtime bridge 检查入口。
3. 修复 editable 安装链路。

### 4.2 兼容层目录治理（已完成）

1. `nanobot` 已迁移到 `packages/nanobot/`。
2. `doctor/bootstrap/runtime_bridge` 已全部切换到新路径。
3. 文档目录树与描述已同步更新。

### 4.3 Milestone 1：单一主控 agent 与安全委派最小链路（已完成）

1. 已实现 `SubagentBackend` 协议与 `host` backend。
2. 已实现角色资产默认生成与角色列表读取。
3. 已实现 `delegate` 命令（角色校验、后端执行、结果归档）。
4. 已实现 `audit list` 命令读取归档。
5. 已支持 `--debug` 输出调试日志。

### 4.4 Milestone 2：容器后端接入准备（validated 阶段，已完成）

1. 已实现 `runtime inspect` 输出运行时依赖明细。
2. 已实现 `runtime validate` 校验 `docker/node/npm/refs` 必需依赖。
3. 已实现 `pyclaw_container` backend 的 validated 执行返回。
4. 已实现 `delegate --backend pyclaw_container ...` 的归档写入链路。

### 4.5 Milestone 3：角色治理最小闭环（已完成）

1. 已实现 `roles show`，可读取角色 `SOUL/ROLE/MEMORY/POLICY`。
2. 已实现 `audit show`，可按 `task_id` 查看单任务归档。
3. 已实现 `roles promote-memory`，可将任务摘要提升写入角色 `MEMORY.md`。
4. 已实现 memory promotion 幂等保护，避免同一 `task_id` 重复写入。

### 4.6 Milestone 4：能力适配接口（已完成，最小闭环）

1. 已定义 `CapabilityAdapter` 合同与能力数据结构。
2. 已实现内置适配器注册表（`host_execution`、`pyclaw_container`、`nanobot_runtime`）。
3. 已实现 `adapters list` 输出适配器与能力清单。
4. 已实现 `tools` 输出工具目录及其适配器来源。

## 5. 下一步

下一阶段进入稳定化与深度实现阶段：

1. 将 `pyclaw_container` 从 `validated` 推进到真实容器执行。
2. 为 `tools` 与 `adapters` 增加权限/策略约束。
3. 逐步补齐 AI 供应商、技能加载与能力适配扩展点。
