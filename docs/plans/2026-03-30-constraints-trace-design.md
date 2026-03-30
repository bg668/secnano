# secnano Minimal Constraints and Trace Design

## Goal

为 secnano 定义一套最小但稳定的结构约束，以及一套可用于 CI 验证主流程正确性的 TraceEvent 设计方案。

目标不是扩展功能，而是让后续 AI 开发更稳定、边界更清晰、测试更可靠。

## Scope

本方案只覆盖两类内容：

1. 最小结构约束
2. TraceEvent 事件模型与 CI 使用方式

本方案刻意不展开：

- 多渠道能力扩展
- 容器隔离增强
- 子代理 / swarm
- 复杂观测平台

## Part 1. Minimal Structural Constraints

### 1. Canonical Terms

下列术语在全仓库中只能表达单一语义：

- `jid`: 聊天目标的稳定标识，是路由主键
- `chat_jid`: 运行时消息所属会话，语义等同于 `jid`，优先保留在消息和任务模型中
- `group_folder`: 该会话对应的工作目录标识，是本地 workspace 键
- `source_group`: IPC 请求发起方的 `group_folder`
- `task_id`: 调度任务主键
- `run_id`: 单次 agent 执行主键
- `trace_id`: 一条端到端流程链路主键，可跨 message / task / reply 复用
- `session_id`: agent 会话连续性标识

约束：

- DB 路由一律以 `jid` 为主键，不再以 `trigger` 或 `folder` 承担路由语义
- `group_folder` 只承担本地目录定位，不参与消息路由判断
- `trace_id` 只表示链路，不表示实体主键

### 2. Module Boundaries

建议把 host 侧职责收敛为 6 个逻辑模块。可以先是目录约束，不要求一次性重构完。

- `ingress`
  - 职责：接收外部输入，包括 channel 消息、chat metadata、IPC task
  - 只做解析、标准化、入 host 流程
- `control_plane`
  - 职责：注册群组、任务管理、权限校验、命令分发
  - 不直接调用具体 agent 实现
- `scheduler`
  - 职责：到期判断、任务入队、运行结果更新
  - 不直接处理 channel
- `runtime`
  - 职责：拉起 agent、收集输出、维护执行上下文
  - 对上提供统一执行接口
- `persistence`
  - 职责：SQLite 读写、schema、状态持久化
  - 不包含业务流程判断
- `adapters`
  - 职责：channel adapter 与 agent adapter
  - 适配外部系统，不承载 host 核心规则

### 3. Dependency Rules

最小依赖规则如下：

- `ingress` 可以依赖 `control_plane`、`persistence`
- `control_plane` 可以依赖 `scheduler`、`runtime`、`persistence`
- `scheduler` 可以依赖 `runtime`、`persistence`
- `runtime` 可以依赖 `persistence`
- `adapters` 可以依赖 host 暴露的接口，但不能绕过 host 直接改核心状态
- `persistence` 不依赖其他业务模块

禁止事项：

- channel adapter 直接写复杂业务规则
- agent runner 直接注册 group 或直接更新任务状态
- scheduler 直接向 channel 发消息
- DB 层返回未经约束的字典拼装业务逻辑

### 4. File Ownership Guidance

建议逐步形成下面的文件归属：

- `secnano/main.py`
  - 只保留启动装配、依赖连接、生命周期管理
- `secnano/ipc.py`
  - 只保留 IPC 读取与标准化，不保留复杂鉴权
- `secnano/task_scheduler.py`
  - 只保留调度与入队，不处理 agent 协议细节
- `secnano/group_queue.py`
  - 只保留队列、串行化、并发治理
- `secnano/db.py`
  - 只保留持久化与 schema
- `secnano/channels/*`
  - 只保留 channel adapter
- `agent_runner/*`
  - 当前实现可保留，但长期应视作某一种 adapter 实现

### 5. Stable Runtime Contract

开放 agent 接口时，host 不应绑定 Anthropic tool-use 风格。建议定义统一的运行契约：

- Host -> AgentInput
  - `run_id`
  - `trace_id`
  - `group_folder`
  - `chat_jid`
  - `is_main`
  - `mode` (`message` | `scheduled_task`)
  - `prompt`
  - `session_id`
  - `context_refs`（可选）

- Agent -> AgentOutput
  - `run_id`
  - `status` (`success` | `error` | `partial`)
  - `reply_text`
  - `session_id`
  - `error`
  - `metrics`（可选）

这样当前 `agent_runner`、未来 `cc`、自研 agent、其他 CLI 都只是不同 adapter。

## Part 2. TraceEvent Design

### 1. Purpose

TraceEvent 的目的不是替代日志，而是提供一套“可断言的流程证据”。

CI 关心的是：

- 主流程有没有发生
- 顺序对不对
- 状态有没有落对
- 关键不变量是否成立

CI 不应该关心：

- 模型具体回复文案
- 完整日志文本
- 非关键调试信息

### 2. Event Shape

建议定义统一事件结构：

```python
@dataclass
class TraceEvent:
    event_id: str
    trace_id: str
    timestamp: str
    category: str
    stage: str
    status: str
    jid: str | None = None
    group_folder: str | None = None
    task_id: str | None = None
    run_id: str | None = None
    source: str | None = None
    details: dict[str, object] | None = None
```

字段约束：

- `trace_id`: 一条完整链路共享
- `category`: 高层类别，如 `message` / `ipc_task` / `scheduled_task` / `agent_run`
- `stage`: 稳定枚举值，CI 直接断言它
- `status`: `success` / `error` / `skip` / `accepted` / `rejected`
- `details`: 只放少量调试信息，不放大文本

### 3. Event Stages

建议先定义最小事件集。

消息主链路：

- `message.received`
- `message.stored`
- `message.group_matched`
- `message.trigger_miss`
- `message.no_registered_group`
- `message.enqueued`

IPC 控制面：

- `ipc_task.received`
- `ipc_task.auth_checked`
- `ipc_task.rejected`
- `ipc_task.group_registered`
- `ipc_task.task_created`
- `ipc_task.task_updated`
- `ipc_task.task_paused`
- `ipc_task.task_resumed`
- `ipc_task.task_canceled`

调度链路：

- `scheduled_task.due`
- `scheduled_task.enqueued`
- `scheduled_task.started`
- `scheduled_task.completed`
- `scheduled_task.failed`
- `scheduled_task.logged`

Agent 链路：

- `agent_run.started`
- `agent_run.prompt_prepared`
- `agent_run.output_received`
- `agent_run.reply_sent`
- `agent_run.completed`
- `agent_run.failed`

### 4. Recommended Emission Points

建议优先在这些节点发事件：

- `_handle_new_message()`
- `_handle_ipc_task()`
- `_enqueue_due_tasks_once()`
- `_handle_scheduled_task()`
- `_process_group_messages()`
- `run_subprocess_agent()` 或未来统一 runtime adapter

原则：

- 一个阶段只发一个稳定事件
- 不要为了“看起来完整”把每个细节都事件化
- 事件优先表达 host 控制面决策，而不是内部临时细节

### 5. Persistence Strategy

最小实现建议分两层：

- 第一层：进程内 ring buffer，供 Web Ops 使用
- 第二层：可选 SQLite `trace_events` 表，供 CI 与故障回放使用

建议表结构：

```sql
CREATE TABLE IF NOT EXISTS trace_events (
    event_id TEXT PRIMARY KEY,
    trace_id TEXT NOT NULL,
    timestamp TEXT NOT NULL,
    category TEXT NOT NULL,
    stage TEXT NOT NULL,
    status TEXT NOT NULL,
    jid TEXT,
    group_folder TEXT,
    task_id TEXT,
    run_id TEXT,
    source TEXT,
    details_json TEXT
);

CREATE INDEX IF NOT EXISTS idx_trace_events_trace_id ON trace_events(trace_id);
CREATE INDEX IF NOT EXISTS idx_trace_events_stage ON trace_events(stage);
CREATE INDEX IF NOT EXISTS idx_trace_events_timestamp ON trace_events(timestamp);
```

### 6. CI Assertions

CI 先做 3 条黄金路径。

路径 A：普通消息触发

- 发送一条普通消息
- 断言事件序列至少包含：
  - `message.received`
  - `message.stored`
  - `message.group_matched`
  - `message.enqueued`
  - `agent_run.started`
  - `agent_run.completed`

路径 B：主组注册新群

- 主组发起 `register_group`
- 断言事件序列至少包含：
  - `ipc_task.received`
  - `ipc_task.auth_checked`
  - `ipc_task.group_registered`
- 同时断言 `registered_groups` 表状态正确

路径 C：定时任务执行

- 构造到期任务
- 断言事件序列至少包含：
  - `scheduled_task.due`
  - `scheduled_task.enqueued`
  - `scheduled_task.started`
  - `scheduled_task.logged`
- 同时断言 `task_run_logs` 与 `scheduled_tasks` 更新正确

### 7. Invariants Worth Testing

除了顺序，还应断言这些不变量：

- 未注册群消息只能 `stored`，不能进入 `agent_run.started`
- 非主组不能产生 `ipc_task.group_registered`
- 同一 `task_id` 在未完成前不能重复 `scheduled_task.started`
- 同一 `jid` 在串行模型下不能并发出现多个活跃 `agent_run.started`
- `reply_sent` 只能发生在 `output_received` 之后

## Recommended Rollout Order

1. 先固定术语和模块职责
2. 再补统一 TraceEvent 结构
3. 再把当前关键路径打点
4. 最后补 CI 黄金路径测试

## Success Criteria

如果这套方案落地，后续 AI 开发应达到以下效果：

- 改动更容易落在正确模块，不再继续把逻辑堆进 `main.py`
- 新接入 agent 时先实现 adapter，而不是直接改 host 主流程
- CI 能稳定判断主流程是否正确，不依赖模型文本结果
- 问题排查时可以按 `trace_id` 还原一条完整链路
