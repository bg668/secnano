# 模块映射 V2

> **注**：本文件是 [`main-to-v2-mapping.md`](./main-to-v2-mapping.md) 的中文译本，内容保持同步。

## 1. 文档目的

本文档将 `main` 实现中的每个当前文件区域和模块映射到 `../architecture/zh/architecture-overview.md` 中定义的具体 V2 架构目标。

对于每个区域，映射说明：

- **当前位置**：代码今天所在的位置。
- **V2 目标**：它属于哪个 V2 模块。
- **操作**：V2 实现期间对它做什么。

操作分类：

| 操作 | 含义 |
|------|------|
| `KEEP AS REF` | 仅作为参考保留；暂不复制到 V2 代码。研究设计和协议。 |
| `MIGRATE LATER` | 可复用；在相关阶段复制并适配到 V2 中。 |
| `REDESIGN` | 需要该概念，但当前实现应从头为 V2 重写。 |
| `SPLIT` | 一个当前文件/区域映射到多个 V2 模块；必须拆分。 |
| `MERGE` | 多个当前文件/区域映射到一个 V2 模块；应合并。 |
| `DEPRECATE` | V2 中不再需要；不延续。 |

---

## 2. 文档（`docs/`）

| 当前文件 | 内容 | V2 目标 | 操作 |
|---------|------|---------|------|
| `docs/README.md` | 导航指南 | 替换为 V2 导航指南 | `REDESIGN` |
| `docs/module_boundary_checklist.md` | 原十二模块架构规范 | `docs/architecture/zh/architecture-overview.md` 在 V2 中取代本文档；在 `main` 中作为历史参考保留 | `KEEP AS REF` |
| `docs/development_milestones.md` | M0–M4 里程碑 | `docs/plan/roadmap.zh-CN.md` 定义 V2 阶段；旧里程碑仅适用于 `main` | `KEEP AS REF` |
| `docs/project_progress.md` | 当前完成状态 | V2 有自己的进展追踪；在 `main` 中保留旧追踪器 | `KEEP AS REF` |
| `docs/architecture/zh/architecture-overview.md` | **V2 架构参考** | 本分支 V2 的规范架构文档 | **新建（本分支）** |
| `docs/mapping/main-to-v2-mapping.zh-CN.md` | **V2 模块映射** | 本文档 | **新建（本分支）** |
| `docs/plan/roadmap.zh-CN.md` | **V2 迁移计划** | V2 分阶段实施路线图 | **新建（本分支）** |

---

## 3. 参考材料（`refs/`）

### 3.1 `refs/pyclaw/` — Python 容器运行时参考

| 区域 | 内容 | V2 目标 | 操作 |
|------|------|---------|------|
| `refs/pyclaw/router.py` | IPC 消息路由 | 六部容器 backend | `KEEP AS REF` |
| `refs/pyclaw/group_queue.py` | 基于分组的任务队列 | 六部容器 backend | `KEEP AS REF` |
| `refs/pyclaw/container_runner.py` | 容器生命周期管理 | 六部容器 backend | `KEEP AS REF` |
| `refs/pyclaw/task_scheduler.py` | 任务调度逻辑 | 六部容器 backend | `KEEP AS REF` |
| `refs/pyclaw/db.py` | 持久层 | 六部工件管理器 / 归档 | `KEEP AS REF` |
| `refs/pyclaw/bus/` | 事件总线与队列 | 六部 IPC 协议参考 | `KEEP AS REF` |
| `refs/pyclaw/channels/` | 通道抽象 | 六部 IPC / 通政司通道适配器 | `KEEP AS REF` |
| `refs/pyclaw/sender_allowlist.py` | 发送方白名单安全 | 门下省策略 / 六部安全 | `KEEP AS REF` |
| `refs/pyclaw/mount_security.py` | 挂载访问控制 | 六部工件管理器安全 | `KEEP AS REF` |

### 3.2 `refs/nanoclaw/` — TypeScript 容器编排参考

| 区域 | 内容 | V2 目标 | 操作 |
|------|------|---------|------|
| `refs/nanoclaw/src/` | 核心 TypeScript 模块（container-runner、group-queue、task-scheduler、IPC） | 六部架构参考 | `KEEP AS REF` |
| `refs/nanoclaw/docs/` | 架构文档（nanorepo-architecture、skills-as-branches、nanoclaw-architecture-final） | 参考六部 + 翰林院/史馆设计 | `KEEP AS REF` |
| `refs/nanoclaw/setup/` | 服务初始化脚本 | 六部启动参考 | `KEEP AS REF` |
| `refs/nanoclaw/.claude/skills/` | 技能实现（Slack、Discord、Gmail、Telegram 等） | 技能注册表格式参考 | `KEEP AS REF` |

**注**：不从 `refs/nanoclaw/` 导入任何代码。TypeScript 代码仅作为架构参考。

---

## 4. 运行时桥接（`secnano/runtime_bridge.py`）

| 当前区域 | 内容 | V2 目标 | 操作 |
|---------|------|---------|------|
| `runtime_bridge.py` | 包裹 `nanobot.agent.loop.AgentLoop` 的垫片 | 中书省 — 认知子层垫片 | `REDESIGN` |

**注**：

- 当前 `runtime_bridge.py` 直接导入 `nanobot` 内部实现，并继承了 `nanobot` 的配置路径假设。
- 在 V2 中，认知子层垫片必须重新设计，以通过稳定的内部接口（`CognitionRequest` → `CognitionResult`）包裹 `nanobot.agent.loop`，不向任何其他层泄露 `nanobot` 内部实现。
- 在认知子层完全重新设计之前，一个最小垫片可以保留在该接口背后以维持 `nanobot` 兼容性。
- V2 中必须**移除** `~/.nanobot` 路径假设和 `nanobot.config.*` 依赖。

---

## 5. 数据模型（`secnano/models.py`）

| 当前区域 | 内容 | V2 目标 | 操作 |
|---------|------|---------|------|
| `models.py` — `DelegateRequest` | 任务委派输入 | 数据 Schema — `Task` / `ExecutionRequest` | `REDESIGN` |
| `models.py` — `DelegateResult` | 委派输出 | 数据 Schema — `ExecutionResult` / `Reply` | `REDESIGN` |
| `models.py` — `TaskArchiveRecord` | 已归档任务记录 | 数据 Schema — `TaskArchiveRecord` | `MIGRATE LATER` |

**注**：

- 当前模型是可用的，但并未完全定义为不可变值对象。
- 在 V2 中，数据 Schema（奏折）层需要严格的 schema 定义，不包含内嵌逻辑。
- `TaskArchiveRecord` 最为稳定，可以以最小改动迁移。
- `DelegateRequest` 和 `DelegateResult` 应重新设计为更丰富的 V2 契约类型（`InboundEvent`、`Task`、`ExecutionRequest`、`ExecutionResult`、`Reply`）。

---

## 6. 委派流程（`secnano/delegate_command.py` 及相关文件）

| 当前区域 | 内容 | V2 目标 | 操作 |
|---------|------|---------|------|
| `delegate_command.py` — 角色选择 | 为任务选择角色 | 中书省 — 编排子层 | `MIGRATE LATER` |
| `delegate_command.py` — backend 选择 | 选择 host vs pyclaw_container | 中书省 → 六部调度 | `MIGRATE LATER` |
| `delegate_command.py` — 结果校验 | 校验执行结果 | 中书省 — 编排子层 | `MIGRATE LATER` |
| `delegate_command.py` — 归档写入 | 写入 TaskArchiveRecord | 归档 / 状态模块 | `MIGRATE LATER` |

**注**：

- 当前委派命令将编排决策、执行调度和归档混合在一个文件中。这对于当前 `main` 基于里程碑的实现是合理的。
- 在 V2 中，这些关注点必须分离到中书省编排、六部执行和归档模块中。
- 角色选择和任务路由逻辑是可复用的，应在 Phase 3 迁移。

---

## 7. 角色与记忆（`secnano/roles.py`、`secnano/roles_command.py`）

| 当前区域 | 内容 | V2 目标 | 操作 |
|---------|------|---------|------|
| `roles.py` — 角色加载 | 从文件系统读取 SOUL/ROLE/MEMORY | 角色与资产模块 | `MIGRATE LATER` |
| `roles.py` — 角色列表 | 列出可用角色 | 角色与资产模块 | `MIGRATE LATER` |
| `roles.py` — 记忆提升 | 将任务洞见提升至角色记忆 | 翰林院/史馆 — 记忆提升 | `SPLIT` |
| `roles_command.py` — CLI 命令 | `roles list`、`roles show`、`roles promote-memory` | 通政司（CLI 入口）→ 命令处理器 | `REDESIGN` |

**注**：

- 角色加载逻辑稳定且可复用；在 Phase 2 迁移到角色与资产模块。
- 记忆提升当前位于 `roles.py`，但在 V2 中属于翰林院/史馆层，需要显式过滤规则；单独提取。
- CLI 命令处理器应重构，使通政司调度 `InboundEvent` 对象，业务逻辑位于相关 V2 模块中。

---

## 8. 审计与归档（`secnano/archive.py`、`secnano/audit_command.py`）

| 当前区域 | 内容 | V2 目标 | 操作 |
|---------|------|---------|------|
| `archive.py` — TaskArchiveRecord 持久化 | 基于 JSON 的任务记录存储 | 归档与状态模块 | `MIGRATE LATER` |
| `archive.py` — 任务列表与检索 | 读取归档记录 | 归档与状态模块 | `MIGRATE LATER` |
| `audit_command.py` — `audit list` / `audit show` | CLI 对归档的读访问 | 通政司调度 → 归档模块查询 | `MIGRATE LATER` |

**注**：

- 归档实现范围明确，与 V2 需求一致。
- V2 主要变更是：归档检索结果应通过翰林院/史馆检索层向 RAG 提供数据，而不是被所有模块直接访问。
- 在 Phase 2 基本原样迁移；在 Phase 4 添加检索接口钩子。

---

## 9. 运行时检查（`secnano/runtime_command.py`）

| 当前区域 | 内容 | V2 目标 | 操作 |
|---------|------|---------|------|
| `runtime_command.py` — `runtime inspect` | 列出已注册的适配器和 backend | 配置管理 / 能力适配器 | `MIGRATE LATER` |
| `runtime_command.py` — `runtime validate` | 校验运行时先决条件 | 配置管理 / doctor | `MIGRATE LATER` |

---

## 10. 适配器与工具（`secnano/adapters/`、`secnano/tools_command.py`）

| 当前区域 | 内容 | V2 目标 | 操作 |
|---------|------|---------|------|
| `adapters/base.py` — `CapabilityAdapter` 协议 | 适配器接口契约 | 能力适配器模块 | `MIGRATE LATER` |
| `adapters/registry.py` — 适配器注册表 | 已注册适配器列表 | 能力适配器模块 | `MIGRATE LATER` |
| `tools_command.py` — 工具目录输出 | 列出可用工具 | 六部 — 工具注册表 | `MIGRATE LATER` |

**注**：

- `adapters/base.py` 中定义的 `CapabilityAdapter` 协议是 V2 的良好起点，但应扩展以包含与 V2 数据 schema 约定一致的 `CapabilityDescriptor` 类型。
- 工具注册表需要从简单目录升级为具有权限执行能力的正式注册表（在六部执行时执行）。

---

## 11. 执行 Backend（`secnano/backends/`）

| 当前区域 | 内容 | V2 目标 | 操作 |
|---------|------|---------|------|
| `backends/base.py` — `ExecutionBackend` 协议 | Backend 接口契约 | 六部 backend 协议 | `MIGRATE LATER` |
| `backends/host.py` — host 执行 | 进程内执行 backend | 六部 — Host Backend | `MIGRATE LATER` |
| `backends/pyclaw_container.py` — 容器校验 | pyclaw 容器 backend（仅校验） | 六部 — 容器 Backend | `REDESIGN` |

**注**：

- `backends/host.py` 是可用且可复用的；在 Phase 5 迁移至六部 Host Backend。
- `backends/pyclaw_container.py` 当前只校验先决条件，不执行真实容器工作负载。在 V2 中，容器 backend 应遵循 `refs/pyclaw` 协议重新设计，实现完整的容器生命周期管理。关键是，V2 容器是 **LLM 驱动的角色执行实例**——每个容器运行自己的 LLM，负责任务细化、步骤规划、工具调用和结果生成。容器 backend 必须支持基于 IPC 的通信（任务投递、状态查询、终止信号），并按角色和全局执行最大活跃容器数量限制。

---

## 12. CLI 入口（`secnano/cli.py`）

| 当前区域 | 内容 | V2 目标 | 操作 |
|---------|------|---------|------|
| `cli.py` — 参数解析与调度 | 主 CLI 调度器 | 通政司 — CLI 入口通道 | `REDESIGN` |

**注**：

- 在 V2 中，CLI 是通政司处理的一个输入通道。CLI 解析器应产出 `InboundEvent` 对象并传递给中书省编排器。
- 当前单体式 `cli.py` 调度模式可以重新设计为轻量级入口通道适配器。

---

## 13. `packages/nanobot/`

| 当前区域 | 内容 | V2 目标 | 操作 |
|---------|------|---------|------|
| `packages/nanobot/` | 当前为空；认知兼容垫片占位符 | 中书省 — 仅认知子层垫片 | `REDESIGN` |

**注**：

- 在 V2 中，`packages/nanobot/` 应**仅**包含将 `nanobot.agent.loop.AgentLoop` 包裹在内部 `CognitionRequest` / `CognitionResult` 接口之后的最小垫片。
- 不得向其他模块暴露任何 `nanobot` 内部实现。
- 不得拥有配置加载、CLI 组装或任何路径约定。

---

## 14. 角色目录（`roles/`）

| 当前区域 | 内容 | V2 目标 | 操作 |
|---------|------|---------|------|
| `roles/general_office/` | 默认角色资产（SOUL、ROLE、MEMORY、技能） | 角色与资产模块 | `MIGRATE LATER` |

**注**：

- 角色资产格式稳定。原样迁移。
- V2 为每个角色增加了显式的 `POLICY.json`。在 Phase 2 中为现有角色添加此文件。

---

## 15. 运行时目录（`runtime/`）

| 当前区域 | 内容 | V2 目标 | 操作 |
|---------|------|---------|------|
| `runtime/tasks/` | 任务归档 JSON 记录 | 归档与状态模块 | `MIGRATE LATER` |
| `runtime/sessions/` | 会话状态（可选） | 归档与状态模块 | `MIGRATE LATER` |

---

## 16. 按 V2 模块汇总

| V2 模块 | 来源（当前文件） | 主要操作 |
|---------|----------------|---------|
| 数据 Schema（奏折） | `models.py`、`delegate_command.py` 类型 | `REDESIGN`（扩展并严格类型化；新增 `ContainerRecord`、带容器绑定的 `SessionState`） |
| 通政司（入口） | `cli.py`、通道适配器 | `REDESIGN`（入口 → InboundEvent） |
| 中书省 — 编排 | `delegate_command.py` 核心逻辑 | `MIGRATE LATER` + `SPLIT` |
| 中书省 — 认知 | `runtime_bridge.py` | `REDESIGN`（稳定接口） |
| 翰林院 / 史馆（RAG + 记忆） | `roles.py` 记忆提升、`archive.py` 检索 | `SPLIT` + 新检索层 |
| 六部 — Host Backend | `backends/host.py` | `MIGRATE LATER` |
| 六部 — 容器 Backend | `backends/pyclaw_container.py`、`refs/pyclaw` | `REDESIGN`（完整生命周期） |
| 六部 — 工具注册表 | `tools_command.py`、`adapters/registry.py` | `MIGRATE LATER` + 扩展 |
| 门下省（输出守卫） | *（尚未实现）* | **新增** |
| 角色与资产 | `roles/`、`roles.py` 加载器 | `MIGRATE LATER` |
| 归档与状态 | `archive.py`、`runtime/tasks/` | `MIGRATE LATER` |
| 能力适配器 | `adapters/base.py`、`adapters/registry.py` | `MIGRATE LATER` + `REDESIGN` descriptor |
| 配置管理 | *（当前极简）* | `REDESIGN`（与 nanobot 解耦） |
| AI Provider | *（尚未实现）* | **新增** |
| 技能注册表 | *（尚未实现）* | **新增** |
| `packages/nanobot/` 垫片 | `runtime_bridge.py` 核心 | `REDESIGN`（隔离在接口之后） |
| `refs/pyclaw` | 仅参考 | `KEEP AS REF` |
| `refs/nanoclaw` | 仅参考 | `KEEP AS REF` |
