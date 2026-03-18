# 迁移计划 V2

> **注**：本文件是 [`migration_plan_v2.md`](./migration_plan_v2.md) 的中文译本，内容保持同步。

## 1. 文档目的

本文档定义了从当前仅含设计的 `architecture-v2` 分支过渡到可工作的 V2 实现的分阶段计划。

配套阅读：

- `docs/architecture_v2.md` — V2 架构规范参考
- `docs/module_mapping_v2.md` — 当前模块到 V2 模块的映射与操作分类

---

## 2. 指导原则

在阅读各阶段之前，请注意以下贯穿整个迁移过程的约束：

### 2.1 当前阶段的非目标（仅设计）

`architecture-v2` 分支当前**仅为文档**。以下内容在 Phase 1 开始之前明确排除在外：

- **不批量移植现有 `secnano/` 实现**。整体复制文件会带入 V2 旨在修复的设计妥协。
- **不过早锁定单一 Agent 框架**。在确定使用 `nanobot` 或任何替代方案之前，中书省认知子层接口必须稳定。
- **在数据 Schema（奏折）达成共识之前不开始实现**。所有其他模块依赖契约类型；在 schema 确定前构建它们是浪费努力。
- **不修改 `main`** 作为 V2 工作的一部分。V2 是一个干净的设计分支；`main` 按自己的里程碑路线继续。
- **不将 `refs/pyclaw` 或 `refs/nanoclaw` 的代码作为生产代码导入**。它们仅是参考材料。

### 2.2 所有阶段均适用的原则

- 每个阶段产出可工作、可测试的交付物——而不仅仅是代码桩。
- 每个阶段维护 `architecture_v2.md` 中定义的模块边界规则。
- 每个模块在下一个模块依赖它之前，先在其契约接口后面实现。
- 从第一个集成测试开始，单一主控约束就要被强制执行。

---

## 3. 阶段总览

| 阶段 | 名称 | 目标 | 先决条件 |
|------|------|------|---------|
| 0 | 架构冻结 | 设计文档完成并达成共识 | — |
| 1 | 数据 Schema 定义 | 所有 V2 契约类型定义并校验 | Phase 0 |
| 2 | 入口（通政司） | CLI 和初始通道适配器产出 InboundEvent | Phase 1 |
| 3 | 归档与角色 | 归档、角色资产加载和记忆提升完成迁移 | Phase 1 |
| 4 | RAG 与记忆检索 | 翰林院/史馆检索层可运行 | Phase 3 |
| 5 | 执行与工具（六部） | Host backend + 工具注册表端到端运行 | Phases 2 & 3 |
| 6 | 容器 Backend | 使用 pyclaw 协议的完整容器生命周期 | Phase 5 |
| 7 | Provider 与认知 | AI Provider 抽象 + 中书省认知重新设计 | Phases 1 & 5 |
| 8 | 输出守卫（门下省） | 输出校验门集成到回复路径 | Phase 7 |
| 9 | 最终迁移与整合 | 端到端 V2 流水线；废弃主兼容垫片 | 所有阶段 |

---

## 4. Phase 0：架构冻结

**状态**：进行中（本分支）。

**目标**：完成并达成 V2 架构设计文档共识。

**交付物**：

- [x] `docs/architecture_v2.md` — V2 模块定义、设计原则、朝廷隐喻
- [x] `docs/module_mapping_v2.md` — 当前到 V2 的映射与操作分类
- [x] `docs/migration_plan_v2.md` — 本文档

**完成标准**：

- 三份文档均在 `architecture-v2` 分支上并经过审查。
- 模块边界、数据契约和依赖规则已达成共识。
- 没有修改任何实现代码。

**本阶段非目标**：

- 不创建或修改 Python 文件（文档除外）。
- 不编写测试。
- 不修改 CLI。

---

## 5. Phase 1：数据 Schema 定义

**目标**：定义所有 V2 契约类型。所有后续阶段都依赖这些类型。

**交付物**：

- `v2/schemas/inbound.py` — `InboundEvent`
- `v2/schemas/task.py` — `Task`、`ExecutionRequest`、`ExecutionResult`
- `v2/schemas/reply.py` — `Reply`
- `v2/schemas/archive.py` — `TaskArchiveRecord`、`SessionState`（包含当前绑定的 `ContainerRecord` 引用）
- `v2/schemas/container.py` — `ContainerRecord`（标识、角色绑定、生命周期状态、IPC 地址、最大槽位配置）
- `v2/schemas/roles.py` — `RoleSpec`
- `v2/schemas/capabilities.py` — `CapabilityDescriptor`
- `v2/schemas/cognition.py` — `CognitionRequest`、`CognitionResult`
- 验证 schema 构造、序列化和不可变性的单元测试。

**设计规则**：

- 所有 schema 必须是不可变值对象（使用 `@dataclass(frozen=True)` 或 Pydantic `BaseModel` with `model_config = ConfigDict(frozen=True)`）。
- schema 内部不包含业务逻辑。
- 除同级 schema 外，不从任何其他 V2 模块导入。

**完成标准**：

- 所有 schema 文件存在并包含完整的字段定义。
- 单元测试通过。
- 每个 schema 至少一个序列化往返测试。

---

## 6. Phase 2：入口（通政司）

**目标**：构建通政司（Tongzhengsi）入口层。CLI 输入产出经校验的 `InboundEvent` 对象。

**交付物**：

- `v2/tongzhengsi/__init__.py`
- `v2/tongzhengsi/cli_channel.py` — 产出 `InboundEvent` 的 CLI 参数解析器
- `v2/tongzhengsi/validator.py` — 输入校验与规范化
- `v2/tongzhengsi/errors.py` — 结构化入口错误类型
- 单元测试：有效输入 → `InboundEvent`；无效输入 → 结构化错误。

**来源映射**：从 `secnano/cli.py` 重新设计。

**设计规则**：

- 通政司不得调用 LLM、加载角色资产或访问归档。
- 输出始终是有效的 `InboundEvent` 或结构化的入口错误。
- 未来通道（API、Slack 等）作为额外通道适配器添加到本模块中。

**完成标准**：

- `python -m secnano_v2 delegate --role <role> --task "<task>"` 产出有效的 `InboundEvent`。
- 格式不合规的输入产出结构化错误，而不是堆栈跟踪。

---

## 7. Phase 3：归档与角色

**目标**：将归档持久层和角色资产加载迁移到 V2 中。

**交付物**：

- `v2/archive/tasks.py` — `TaskArchiveRecord` 持久化（JSON 或 SQLite）
- `v2/archive/sessions.py` — `SessionState` 持久化
- `v2/archive/queries.py` — 归档查询读接口
- `v2/roles/loader.py` — 角色资产加载（SOUL、ROLE、MEMORY、技能、POLICY）
- `v2/roles/registry.py` — 内存角色注册表
- `v2/roles/memory.py` — 带过滤规则的记忆提升
- 单元测试：归档往返；从文件系统加载角色；记忆提升规则。

**来源映射**：

- `archive.py` → `v2/archive/tasks.py`（迁移）
- `roles.py` 加载器 → `v2/roles/loader.py`（迁移）
- `roles.py` promote-memory → `v2/roles/memory.py`（拆分）

**完成标准**：

- 使用 V2 schema 类型可以写入和读取归档记录。
- 从 `roles/` 目录加载角色资产到 `RoleSpec` 对象。
- 记忆提升只将经过过滤的洞见写入 `MEMORY.md`。

---

## 8. Phase 4：RAG 与记忆检索（翰林院 / 史馆）

**目标**：构建向认知子层提供上下文的翰林院/史馆检索层。

**交付物**：

- `v2/hanlin/__init__.py`
- `v2/hanlin/retriever.py` — 对已归档记录和角色记忆的查询接口
- `v2/hanlin/indexer.py` — 索引管理（简单关键词或基于嵌入）
- `v2/hanlin/memory_gate.py` — 提升过滤规则（只有经过过滤的洞见 → 长期记忆）
- 单元测试：检索查询返回相关记录；提升门拒绝未过滤的原始输出。

**设计规则**：

- 检索层从认知子层的视角来看是只读的（不写入）。
- 记忆提升只通过 `memory_gate.py` 写入，从不直接写入。
- 先从简单关键词匹配开始；在后续迭代中添加基于嵌入的检索。

**完成标准**：

- 认知子层可以按关键词查询相关上下文。
- 记忆门正确阻止原始执行输出进入长期记忆。

---

## 9. Phase 5：执行与工具（六部）

**目标**：构建带有可工作 host backend 和工具注册表的六部执行层。

**交付物**：

- `v2/liubu/__init__.py`
- `v2/liubu/backends/base.py` — `ExecutionBackend` 协议
- `v2/liubu/backends/host.py` — Host 执行 backend
- `v2/liubu/tools/registry.py` — 工具定义和调度
- `v2/liubu/tools/specs.py` — 工具 schema 类型
- `v2/liubu/artifacts.py` — 工件收集与打包
- 集成测试：host backend 接收 `ExecutionRequest`、执行、返回 `ExecutionResult`。

**来源映射**：

- `backends/base.py` → `v2/liubu/backends/base.py`（迁移）
- `backends/host.py` → `v2/liubu/backends/host.py`（迁移）
- `adapters/base.py` → 参考 schema 中的 `CapabilityDescriptor` + `v2/liubu/backends/base.py`

**完成标准**：

- Host backend 使用 V2 schema 类型端到端执行一个简单任务。
- 工具注册表列出并调度至少一个内置工具。
- 执行后将 `ExecutionResult` 写入归档。

---

## 10. Phase 6：容器 Backend

**目标**：实现完整的容器执行 backend，遵循 `refs/pyclaw` 协议。每个容器是由 LLM 驱动的角色执行实例，而不是简单的命令沙箱。

**交付物**：

- `v2/liubu/backends/container.py` — 完整容器生命周期管理（启动、挂载、IPC、回收）
- `v2/liubu/container/workspace.py` — 工作区挂载
- `v2/liubu/container/mounts.py` — 挂载控制（角色资产、技能、工件）
- `v2/liubu/container/secrets.py` — 密钥注入
- `v2/liubu/container/lifecycle.py` — 容器启动 / 监控 / 停止 / 回收
- `v2/liubu/container/ipc.py` — IPC 协议（遵循 `refs/pyclaw/bus/`）：任务投递、状态查询、补充上下文、中断、终止
- `v2/liubu/container/slots.py` — 活跃容器槽位管理（全局上限 + 按角色上限；超出上限时排队/等待）
- `v2/liubu/container/writeback.py` — 回收前状态回写：状态摘要、工件索引、结果、记忆候选 → 归档与状态
- 需要本地容器运行时的集成测试。

**来源映射**：

- `refs/pyclaw/container_runner.py` → 仅作为协议参考；原生重新实现。
- `refs/pyclaw/bus/` → IPC 参考；原生重新实现。
- `backends/pyclaw_container.py` → 废弃；用重新设计的实现替代。

**设计规则**：

- 容器内 LLM 负责任务细化、步骤规划、工具调用、中间判断和结果生成。中书省不介入这些内部决策。
- 中书省仅通过 IPC 与容器通信。IPC 消息携带：新任务分配、补充上下文、状态查询、中断信号和终止命令。
- `Session` 应尽可能路由到其当前绑定的 `Container`。容器槽位管理必须追踪哪个会话绑定到哪个容器。
- 容器在被回收之前必须回写所有持久状态。

**完成标准**：

- 使用 V2 schema 类型可以将任务委派给容器 backend。
- 容器内 LLM 完成任务并通过 IPC 产出 `ExecutionResult`。
- 会话绑定得到保持：对同一会话的后续请求路由到同一容器。
- 达到活跃容器上限时，新任务排队而不是产生额外容器。
- 密钥不在容器范围外写入磁盘。
- 回收前容器回写完成。

---

## 11. Phase 7：Provider 与认知（中书省大脑）

**目标**：构建 AI Provider 抽象，并在稳定的内部接口后面重新设计中书省认知子层。

**交付物**：

- `v2/providers/base.py` — `AIProvider` 协议
- `v2/providers/registry.py` — Provider 注册表与选择
- `v2/providers/factory.py` — 从配置创建 Provider 的工厂
- `v2/zhongshu/cognition/runtime.py` — 认知子层入口点（`CognitionRequest` → `CognitionResult`）
- `v2/zhongshu/cognition/prompting.py` — 从角色资产和翰林院上下文组装提示词
- `v2/zhongshu/cognition/loop.py` — 带工具调用反馈的多轮 LLM 调用循环
- `v2/zhongshu/cognition/nanobot_shim.py` — **可选**垫片，将 `nanobot.agent.loop.AgentLoop` 包裹在接口之后（如果仍在使用 `nanobot`）
- 单元测试：从 `RoleSpec` + 检索上下文组装提示词；Provider 抽象返回标准响应。

**设计规则**：

- `nanobot`（如使用）只从 `nanobot_shim.py` 调用。其他文件不导入 `nanobot`。
- 认知子层接口（`CognitionRequest` / `CognitionResult`）必须在 `nanobot_shim.py` 被原生实现替代之前保持稳定。

**完成标准**：

- 带有角色和任务的 `CognitionRequest` 产出带有自然语言结论的 `CognitionResult`。
- 切换 Provider（例如从 OpenAI 到 Anthropic）只需更改配置，无需修改代码。
- 所有工具调用循环在认知子层内完成；没有工具结果以原始字符串泄露给编排器。

---

## 12. Phase 8：输出守卫（门下省）

**目标**：将门下省（Menxia Sheng）输出守卫实现为回复路径中的显式校验门。

**交付物**：

- `v2/menxia/__init__.py`
- `v2/menxia/guard.py` — 输出校验入口点（`Reply` → `ApprovedReply | Rejection`）
- `v2/menxia/policies/base.py` — 策略规则协议
- `v2/menxia/policies/format.py` — 格式校验规则
- `v2/menxia/policies/safety.py` — 内容安全规则（初始宽松；按角色收紧）
- 单元测试：已审批的回复通过；拒绝返回结构化错误。

**设计规则**：

- 守卫不生成内容，只检查并审批或拒绝。
- 策略规则是声明式的，不调用 LLM。
- 拒绝反馈给中书省编排器，而不是直接给用户。

**完成标准**：

- V2 编排器中的每条回复路径在到达 I/O 输出层之前都经过守卫。
- 策略违规产出结构化拒绝，而不是原始模型输出。

---

## 13. Phase 9：最终迁移与整合

**目标**：完成端到端 V2 流水线，废弃主兼容垫片，并验证完整架构。

**交付物**：

- `v2/zhongshu/orchestrator/` — 完整编排子层（会话、规划器、调度器、审查器）
- 端到端集成测试：CLI 输入 → InboundEvent → 编排器 → 认知 → 执行 → 输出守卫 → 回复。
- 废弃 `packages/nanobot/nanobot_shim.py`（或在 `nanobot` 不再需要时以原生循环替代）。
- 更新 `docs/project_progress.md`（V2 部分）的完成状态。
- 决策记录：保留 `nanobot` 作为库垫片，还是以原生认知循环替代。

**完成标准**：

- 完整的委派任务（角色选择 → 认知 → 执行 → 归档 → 回复）只使用 V2 模块完成。
- 除 `v2/zhongshu/cognition/nanobot_shim.py` 外，没有其他模块导入 `nanobot` 内部实现。
- 单一主控约束通过集成测试验证。
- 所有原 `main` 里程碑命令都有 V2 等价命令。

---

## 14. 迁移阶段汇总

| 阶段 | 引入的关键模块 | 关键来源 | 风险 |
|------|--------------|---------|------|
| 0 | 文档 | — | 低 |
| 1 | 数据 Schema（奏折） | `models.py` → 重新设计 | 低 |
| 2 | 通政司（入口） | `cli.py` → 重新设计 | 低 |
| 3 | 归档 + 角色 | `archive.py`、`roles.py` → 迁移 | 低 |
| 4 | 翰林院 / 史馆（RAG + 记忆） | 新层 | 中 |
| 5 | 六部 Host Backend + 工具 | `backends/host.py` → 迁移 | 中 |
| 6 | 六部容器 Backend | `refs/pyclaw` → 重新实现 | 高 |
| 7 | AI Provider + 中书省认知 | `runtime_bridge.py` → 重新设计 | 高 |
| 8 | 门下省（输出守卫） | 新层 | 中 |
| 9 | 编排 + 整合 | `delegate_command.py` → 重新设计 | 高 |

---

## 15. V2 实现建议目录结构

实现开始时，V2 代码应放置在 `v2/` 包中，与现有 `secnano/` 包并列（不替换），直到 Phase 9 整合：

```
secnano/                        ← 现有实现（不修改）
v2/                             ← 新 V2 实现
  schemas/                      ← Phase 1：数据 Schema（奏折）
    inbound.py
    task.py
    reply.py
    archive.py
    container.py
    roles.py
    capabilities.py
    cognition.py
  tongzhengsi/                  ← Phase 2：入口
    cli_channel.py
    validator.py
    errors.py
  archive/                      ← Phase 3：归档与状态
    tasks.py
    sessions.py
    queries.py
  roles/                        ← Phase 3：角色与资产
    loader.py
    registry.py
    memory.py
  hanlin/                       ← Phase 4：RAG + 记忆检索
    retriever.py
    indexer.py
    memory_gate.py
  liubu/                        ← Phases 5 & 6：执行 + 工具
    backends/
      base.py
      host.py
      container.py
    container/
      workspace.py
      mounts.py
      secrets.py
      lifecycle.py
      ipc.py
      slots.py                  ← 活跃容器槽位管理 + 排队
      writeback.py              ← 回收前状态回写到归档
    tools/
      registry.py
      specs.py
    artifacts.py
  providers/                    ← Phase 7：AI Provider
    base.py
    registry.py
    factory.py
  zhongshu/                     ← Phases 7 & 9：主控 + 大脑
    cognition/
      runtime.py
      prompting.py
      loop.py
      nanobot_shim.py           ← 可选，隔离 nanobot 依赖
    orchestrator/
      sessions.py
      planner.py
      dispatcher.py
      reviewer.py
  menxia/                       ← Phase 8：输出守卫
    guard.py
    policies/
      base.py
      format.py
      safety.py
  config/                       ← 支撑：配置管理
    schema.py
    loader.py
    paths.py
  skills/                       ← 支撑：技能注册表
    loader.py
    registry.py
    parser.py
  adapters/                     ← 支撑：能力适配器
    base.py
    registry.py
    capability_specs.py
docs/                           ← V2 设计文档（本分支）
refs/                           ← 参考材料（不修改）
packages/
  nanobot/                      ← 仅认知垫片；无其他 nanobot 接触面
roles/                          ← 角色资产（迁移时添加 POLICY.json）
runtime/                        ← 运行时数据（归档、会话、工件）
```
