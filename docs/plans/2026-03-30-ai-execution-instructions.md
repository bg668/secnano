# secnano AI Execution Instructions

## Purpose

本说明用于指导 AI 在 secnano 仓库内持续开发。

目标不是泛化扩展平台，而是围绕当前定位，逐步把以下五项能力做扎实：

- 任务接收
- 编排
- 调度
- 记录
- 开放 agent 接口

本说明以 [2026-03-30-constraints-trace-design.md](/D:/Work/01_processing/secnano/docs/plans/2026-03-30-constraints-trace-design.md) 为上位约束。

## Product Boundary

当前阶段只做 host orchestrator 核心，不做额外扩展。

不要主动扩展：

- 新 channel 能力
- 容器隔离增强
- 多 agent swarm
- 复杂监控平台
- 非必要 UI 改造

优先做的是把 host 主流程和控制面做完整、稳定、可验证。

## Fixed Decisions

以下 4 个决策已经锁定，AI 不应再次发散讨论，除非用户明确要求修改。

### 1. TraceEvent persistence

采用双层方案：

- 进程内 ring buffer，用于 Web Ops 展示
- SQLite `trace_events` 表，用于 CI 断言与故障回放

不要只做日志文件。
不要只做内存态事件。

### 2. Agent adapter strategy

采用两步走：

- 第一步：把当前 `agent_runner` 视为 `runtime adapter v1`
- 第二步：Host 面向统一 `AgentInput / AgentOutput` 契约

当前阶段不要同时接入 `cc`、自研 agent、其他 CLI。
先把现有 Anthropic subprocess 路径抽象成标准 adapter。

### 3. `main.py` refactor strategy

采用渐进拆分，不做一次性大重构。

第一轮只优先拆出：

- message ingress
- IPC task control plane
- runtime orchestration

`main.py` 保留：

- 启动装配
- 依赖连接
- 生命周期管理

### 4. CI first batch

第一批 CI 只覆盖 3 条黄金路径：

- 普通消息流
- 主组注册流
- 定时任务流

不要在第一轮就铺满所有边角场景。

## Structural Constraints

AI 在修改代码时，必须遵守以下最小结构约束。

### Canonical Terms

- `jid`: 路由主键
- `chat_jid`: 消息或任务运行时所属聊天
- `group_folder`: 本地 workspace 键，不承担路由语义
- `source_group`: IPC 请求发起方 folder
- `task_id`: 调度任务主键
- `run_id`: 单次 agent 执行主键
- `trace_id`: 流程链路主键
- `session_id`: 会话连续性标识

禁止混用：

- 不要把 `group_folder` 当成消息路由键
- 不要把 `trigger` 当成 group 主键
- 不要把 `trace_id` 当实体主键

### Module Responsibilities

目标职责分层如下：

- `ingress`: 接收 message / metadata / IPC task
- `control_plane`: group 注册、任务管理、鉴权、命令分发
- `scheduler`: 到期判断、任务入队、结果更新
- `runtime`: agent 执行、输出采集、执行上下文
- `persistence`: DB schema 与持久化
- `adapters`: channel adapter 与 agent adapter

禁止事项：

- channel adapter 直接写核心业务规则
- scheduler 直接向 channel 发消息
- agent runner 直接注册 group 或直接更改任务状态
- DB 层承载复杂流程判断

## Legacy Cleanup Policy

仓库中可能存在历史遗留代码。不要一次性大扫除，采用“先去噪，再开发，最后收尾”的策略。

### A 类：开发前先处理

满足以下任一条件的遗留代码，在主线开发前优先清理或标注：

- 会误导 AI 认为能力已经可用
- 名称与当前主线能力冲突
- 明显未接通，却看起来像正式实现
- 已经废弃但靠近主入口，容易被继续引用

允许的动作：

- 删除低风险死代码
- 移除未使用入口
- 给保留代码加清晰注释，注明“未启用 / 历史遗留 / 不要复用”
- 在文档或 TODO 中列出待收尾项

### B 类：开发后再处理

以下内容不要在主线开发前花太多时间：

- 与本轮任务无关的边角模块
- 需要等新实现稳定后才能判断是否删除的旧逻辑
- 可能影响兼容性的历史路径

### C 类：不确定是否仍有用

先不要贸然删除。
优先：

- 标注用途不明
- 搜索调用点
- 在本轮改造完成后再决定去留

### Cleanup Principle

清理的目标不是“仓库最整洁”，而是“减少 AI 误判和错误复用”。

## Implementation Order

AI 执行时，按以下顺序推进：

### Phase 1. 去噪与边界固定

- 识别并处理 A 类遗留代码
- 固定术语与模块职责
- 在需要的位置补注释或文档，避免误用

### Phase 2. Runtime contract

- 定义统一 `AgentInput / AgentOutput`
- 让当前 `agent_runner` 适配这一契约
- Host 改为依赖 runtime 接口，而不是依赖具体实现细节

### Phase 3. TraceEvent

- 定义 `TraceEvent` 数据结构
- 新增 `trace_events` 表
- 增加进程内 ring buffer
- 在关键路径上补稳定事件点

### Phase 4. Golden path tests

- 普通消息流测试
- 主组注册流测试
- 定时任务流测试

测试优先断言：

- 事件序列
- 关键 DB 状态
- 不变量

不要优先断言：

- LLM 具体回复文本
- UI 细节
- 完整日志输出

## TraceEvent Rules

事件只表达 host 控制面关键阶段，不追求过细。

最低事件集：

- `message.received`
- `message.stored`
- `message.group_matched`
- `message.trigger_miss`
- `message.no_registered_group`
- `message.enqueued`
- `ipc_task.received`
- `ipc_task.auth_checked`
- `ipc_task.rejected`
- `ipc_task.group_registered`
- `scheduled_task.due`
- `scheduled_task.enqueued`
- `scheduled_task.started`
- `scheduled_task.completed`
- `scheduled_task.failed`
- `scheduled_task.logged`
- `agent_run.started`
- `agent_run.prompt_prepared`
- `agent_run.output_received`
- `agent_run.reply_sent`
- `agent_run.completed`
- `agent_run.failed`

规则：

- 一个稳定阶段只发一个事件
- 事件名固定，不随实现细节变化
- `details` 只放少量调试字段，不放大文本

## CI Acceptance

第一轮 CI 通过标准：

### Path A. 普通消息流

至少断言事件序列包含：

- `message.received`
- `message.stored`
- `message.group_matched`
- `message.enqueued`
- `agent_run.started`
- `agent_run.completed`

### Path B. 主组注册流

至少断言事件序列包含：

- `ipc_task.received`
- `ipc_task.auth_checked`
- `ipc_task.group_registered`

并断言 `registered_groups` 状态正确。

### Path C. 定时任务流

至少断言事件序列包含：

- `scheduled_task.due`
- `scheduled_task.enqueued`
- `scheduled_task.started`
- `scheduled_task.logged`

并断言 `task_run_logs` 与 `scheduled_tasks` 状态正确。

## Invariants

AI 在实现和测试时，必须保护以下不变量：

- 未注册群消息不能进入 `agent_run.started`
- 非主组不能完成 group 注册
- 同一 `task_id` 未完成前不能重复开始
- 同一 `jid` 在串行模型下不能并发活跃执行
- `reply_sent` 不能早于 `output_received`

## Working Style for AI

执行时遵守以下工作方式：

- 每次改动尽量小步
- 优先补测试或可验证事件，再补实现
- 不做一次性大重构
- 不主动扩大范围
- 不因为“顺手”增加额外 feature
- 每完成一个阶段，优先清理该阶段新增的临时兼容代码

## Done Definition

当以下条件同时满足时，本轮工作才算完成：

- 结构边界比当前更清晰
- 当前 runtime 已进入统一 adapter 契约
- TraceEvent 已可用于 CI 断言
- 三条黄金路径测试存在且稳定
- 没有继续增加新的历史遗留噪音
