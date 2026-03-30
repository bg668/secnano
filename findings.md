# Findings

## Product Positioning Context
- 当前仓库 README 明确写的是 “Python AI agent orchestrator with subprocess isolation”，并说明它是 `nanoclaw` 的 Python translation。
- 从定位上看，核心不是做“大而全的 agent 平台”，而是做一个小而清晰的 host orchestrator：接消息、存状态、按组路由、调度任务、拉起 agent、回传结果。
- `nanoclaw` 的哲学是核心系统保持小、扩展通过 skill/接入完成；这意味着 secnano 当前最重要的是把主闭环做扎实，而不是提前做很多外围能力。

## Current Architecture Discoveries
- 主入口集中在 `secnano/main.py`，当前已经具备 host 进程、SQLite、IPC watcher、调度器、队列、agent runner、web channel 的完整骨架。
- `LocalWebChannel` 是目前唯一内建 channel，说明“多渠道接入架构”已有抽象，但“实际多渠道能力”仍停留在单一实现。
- `registered_groups` 已经升级为以 `jid` 为核心字段，路由走 `get_registered_group_by_jid()`，这比早期按 folder/trigger 绑定更贴近目标定位。
- `register_group` 已通过 agent 工具 -> IPC task -> host 鉴权 -> DB 落库 -> 目录初始化形成闭环，但 IPC 任务类型目前基本只覆盖这个能力。
- 调度器已实现 `once / interval / cron` 三种计划模型，并会把到期任务送入 per-group queue，避免同组直接并发执行。
- Agent 执行已从 Docker/container 语义替换为 Python subprocess + 轻量 tool loop；这让本地开发更轻，但隔离能力明显弱于 nanoclaw。
- 记录能力比“最小可用”更强：已包含 messages、chats、sessions、scheduled_tasks、task_run_logs、recent_events、recent_agent_runs，以及一个本地 ops dashboard。

## Gap Discoveries Against Target
- “任务接收”层面：消息、chat metadata、register_group IPC 已有；但任务控制面还不完整，缺少创建后管理任务的 host API / IPC 能力闭环。
- “编排”层面：当前编排主要体现在 per-group queue 和主组授权注册，尚未形成清晰的 host-side orchestration contract，例如统一任务命令模型、agent 能力描述、运行状态机。
- “调度”层面：基础可用，但 `interval` 是以当前时间加秒数计算下次运行，存在相对时间漂移风险；与 nanoclaw 的“锚定已计划时间”相比更偏 MVP。
- “记录”层面：运行记录相对完整，但缺少可恢复、可审计的“任务生命周期视图”，例如任务操作日志、IPC task 处理结果、失败重试语义。
- “开放 agent 接口”层面：目前真正开放的是 Anthropic tool-use 风格的自研 runner，不是通用 agent adapter；要接自己的 agent、`cc` 或其他 CLI，还缺一层稳定的适配协议。
- `MAX_CONCURRENT_SUBPROCESSES` 已在配置中定义，但当前 `GroupQueue` 未使用它做全局并发控制，说明“编排器”还有关键的资源调度缺口。
- 测试覆盖较薄，当前只有 2 个测试文件，覆盖点主要是 D0 核心链路和 web channel，距离“可持续演进的 orchestrator”还有明显差距。

## First-Round Planning Notes
- `secnano/main.py` 同时承载 message ingress、IPC control plane、runtime orchestration、ops snapshot，且关键主链路函数集中在 [995] `_process_group_messages`、[1206] `_handle_ipc_task`、[1292] `_handle_new_message`、[1392] `_handle_scheduled_task`，符合“渐进拆分 main.py”的优先改造对象。
- 当前“trace timeline”来自 `secnano/logger.py` 的 `_RECENT_EVENTS` 与 `main.py` 的 `_recent_agent_runs` 拼装，不是文档要求的稳定 `TraceEvent` 模型；这块看起来可观察，但不适合直接拿来做 CI 断言，属于应先去噪/替换的 A 类邻近主入口实现。
- `secnano/task_scheduler.py` 已有 `_queued_task_ids` 去重与 `task_run_logs` 持久化，但没有 `trace_events` 持久化，也没有把 `scheduled_task.due/enqueued/started/logged` 显式建模出来，说明“记录”闭环还没形成可断言控制面。
- `secnano/subprocess_runner.py` 仍直接暴露 `SubprocessInput/SubprocessOutput` 语义，host 侧没有独立 `AgentInput/AgentOutput` 契约；这正是“先把当前 agent_runner 抽象为 runtime adapter v1”的最小切口。
- 现有测试 `tests/test_devplan_d0.py` 只验证局部行为，没有对三条黄金路径做稳定事件序列断言；第一轮应在现有测试文件基础上补黄金路径，而不是先扩展更多测试面。

## Batch 1 Implementation Findings
- `secnano/types.py` 现已补入 `TraceEvent`、`AgentInput`、`AgentOutput`，且保留旧 `SubprocessInput/SubprocessOutput` 作为兼容层，符合“先抽象 contract，不一次性替换旧执行路径”的约束。
- `secnano/db.py` 已新增 `trace_events` 表与 `insert_trace_event()/list_trace_events()`；这意味着 Trace 已经不再只能依赖 `logger.py` 的 recent log。
- `secnano/trace.py` 提供了最小 `TraceStore`，实现 ring buffer + SQLite 双写，已满足固定决策中的 persistence 方案。
- `secnano/runtime.py` 提供 `SubprocessRuntimeAdapter`，将 `AgentInput` 映射为旧 `SubprocessInput`，并将 `SubprocessOutput` 转为 `AgentOutput`；这完成了 runtime adapter v1 的第一层抽象。
- 当前尚未把 `main.py` 切到 `TraceStore` 和 `SubprocessRuntimeAdapter` 上，所以业务主链路仍未真正使用新 contract；下一批需要进入事件接入与主流程替换。

## Batch 2 Implementation Findings
- `secnano/main.py` 已新增 `_trace_store`、`_get_runtime_adapter()`、`_emit_trace()`，消息主链路不再只依赖 structlog，而是把稳定事件写入正式 `trace_events`。
- `_process_group_messages()` 已切到 `AgentInput`/`AgentOutput` + `SubprocessRuntimeAdapter`，说明 host 已开始依赖统一 runtime contract，而不是直接依赖旧 subprocess 数据结构。
- 普通消息流目前已发出 `message.received / stored / group_matched / enqueued` 与 `agent_run.started / prompt_prepared / output_received / completed`，满足第一条黄金路径的最小断言需求。
- IPC 注册流目前已发出 `ipc_task.received / auth_checked / group_registered`，并在未授权时额外发出 `ipc_task.rejected`，满足第二条黄金路径的最小断言需求。
- 定时任务路径已同步切到 runtime adapter，但还没有补齐 `scheduled_task.due / enqueued / started / logged` 的稳定 TraceEvent；这将是下一批最合理的收尾点。

## Batch 3 Implementation Findings
- `secnano/trace.py` 现在提供了进程级 `get_trace_store()`，`main.py` 与 `task_scheduler.py` 共用同一个默认 trace store，符合“ring buffer + SQLite”双层记录的方向，而不是各自维护分裂的事件缓冲。
- `secnano/task_scheduler.py` 已补上 `_emit_trace()`，并在 `_enqueue_due_tasks_once()` 发出 `scheduled_task.due / enqueued`，在 `_run_task()` 发出 `scheduled_task.started / completed|failed / logged`。
- 这样一来，第一轮要求的三条黄金路径都已经能在 `trace_events` 中做稳定断言，不再依赖日志文本或模型输出内容。
- 当前尚未完成的重点已经从“黄金路径可断言”转到“主入口渐进拆分”和“A 类遗留去噪”，尤其是 `main.py` 内的 ops timeline / recent log 拼装仍容易和正式 TraceEvent 混淆。

## Batch 4 Implementation Findings
- `secnano/ingress.py` 现在承接了 chat metadata 持久化与普通消息接收逻辑，`secnano/control_plane.py` 承接了 IPC `register_group` 控制面逻辑；这让 `main.py` 不再直接堆积这两块实现细节。
- `main.py` 目前对 ingress 与 control plane 的形态已经接近 wiring 层：保留依赖连接、生命周期与少量运行时 orchestration，而不是继续膨胀所有主链路细节。
- 这一步没有改变现有对外调用点，现有测试仍然通过，说明“渐进拆分、不做一次性重构”的策略是成立的。
- 仍需优先处理的 A 类遗留点是 `main.py` 中基于 recent log / recent agent run 拼装的 ops timeline，因为它和正式 TraceEvent 系统在语义上仍然过于接近，容易误导后续开发。

## Batch 5 Implementation Findings
- `secnano/runtime_orchestration.py` 已正式承接 message runtime orchestration 与 scheduled-task runtime orchestration，`main.py` 中 `_process_group_messages()` 与 `_handle_scheduled_task()` 现在都只是对 orchestrator 的薄包装。
- 到此为止，`main.py` 的三块优先拆分目标都已触达：
  - message ingress -> `secnano/ingress.py`
  - IPC task control plane -> `secnano/control_plane.py`
  - runtime orchestration -> `secnano/runtime_orchestration.py`
- `secnano/logger.py:get_recent_events()` 与 `main.py` 的 ops snapshot 组装位置已补上说明，明确它们是 ops/debug 视图，而不是正式 TraceEvent source；这已经对 A 类遗留误导做了第一轮去噪。
- 仍未完成的清理是“进一步缩减 `main.py` 中 ops snapshot / timeline 组装代码量”以及“决定 recent log 视图长期是否继续保留”；这已经不再阻塞 host orchestrator 第一轮核心目标。

## Batch 6 Implementation Findings
- `secnano/ops_view.py` 现在承接了 ops/debug payload 的视图组装逻辑，`main.py` 中 `_build_ops_snapshot()` 只负责采集 host 当前数据再委托给独立 builder。
- `main.py` 中原本那批本地 `_matches_filter_text/_filter_items/_build_trace_tokens/_derive_ops_summary/_build_graph_snapshot/_build_timeline` helper 已被移除，靠近主入口的“第二套 ops 实现”噪音已经清掉。
- 这意味着第一轮 A 类遗留处理目标在当前范围内已经完成：容易让后续开发误以为“formal trace = recent log/ops timeline”的近入口死辅助代码已不再存在。
- 仍然保留的 recent log 视图本身是有意存在的 ops/debug 能力，不再属于“看起来像正式主线实现但实际会误导开发”的 A 类问题。

## Maturity Assessment Notes
- 以 MVP 视角：主闭环已经成形，尤其是 web main group、自注册、消息触发、任务调度、agent 回传这几条关键链路。
- 以实用阶段视角：已经能做本地单机场景演示甚至小范围自用，但在多 agent 接入、资源治理、任务管理、失败恢复方面还不够稳。
- 以完整产品视角：当前更像“可运行原型 + 有意识的控制面雏形”，还不是一套边界清晰、协议稳定、可长期演进的产品内核。
