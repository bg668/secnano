# Host Orchestrator Round 1 Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** 在不扩大产品边界的前提下，为 secnano 建立 runtime contract、TraceEvent 和三条黄金路径测试的最小闭环，并开始按约束渐进拆分 `main.py`。

**Architecture:** 第一轮不做大重构，只做“先立契约，再补可断言记录，再把主链路从 `main.py` 拆出最小边界”的渐进式改造。当前 `agent_runner` 保留为 runtime adapter v1，TraceEvent 采用 ring buffer + SQLite 双层持久化，并让测试优先围绕普通消息流、主组注册流、定时任务流建立稳定断言。

**Tech Stack:** Python 3.11+, asyncio, SQLite, structlog, pytest, pytest-asyncio

---

## Current State Summary

- `secnano/main.py` 已形成可运行骨架，但同时承载 message ingress、IPC task control plane、runtime orchestration 和 ops snapshot，主链路边界不清。
- `secnano/logger.py` 的 `_RECENT_EVENTS` 和 `main.py` 的 `_recent_agent_runs` 目前更像调试视图，不是稳定 `TraceEvent` 契约。
- `secnano/subprocess_runner.py` 直接暴露当前 subprocess 运行语义，host 侧尚无统一 `AgentInput / AgentOutput`。
- `tests/test_devplan_d0.py` 有局部验证，但还没有文档要求的三条黄金路径事件序列测试。

## Smallest First Step

先做 `TraceEvent` 基础设施与最小 runtime contract 类型定义，不先动大块流程。

原因：

- 这是后续拆 `main.py`、补黄金路径测试、抽象 runtime adapter 的共同底座。
- 一旦先写测试而没有稳定事件模型，测试会继续绑在 structlog 文案或临时字段上，后面会反复返工。
- 这一步改动可控，能快速产生可断言的新接口与新表结构，适合“小步可验证”。

## Priority Plan

### Priority 1. 统一 runtime contract 与 TraceEvent 底座

**目标**

- 定义 host 面向的 `AgentInput / AgentOutput`
- 定义稳定 `TraceEvent`
- 建立 ring buffer + SQLite `trace_events` 持久化能力
- 先不改产品边界，不引入新 agent

**Files**

- Modify: `secnano/types.py`
- Modify: `secnano/db.py`
- Create: `secnano/trace.py`
- Create: `secnano/runtime.py`
- Modify: `secnano/subprocess_runner.py`
- Modify: `secnano/main.py`
- Test: `tests/test_trace_events.py`

**Planned Changes**

- 在 `secnano/types.py` 新增 `TraceEvent`、`AgentInput`、`AgentOutput`，并保留现有 `SubprocessInput/SubprocessOutput` 作为兼容层，避免一次性替换。
- 在 `secnano/db.py` 增加 `trace_events` 表及对应 insert/list 查询方法，不把 TraceEvent 混进现有 recent log 结构。
- 新建 `secnano/trace.py`，封装 ring buffer、事件写入、按 `trace_id`/stage 查询。
- 新建 `secnano/runtime.py`，定义 runtime adapter v1 接口，以及“当前 subprocess runner 如何从 `AgentInput` 转成 subprocess 调用”的适配层。
- 在 `secnano/subprocess_runner.py` 保留实际子进程执行逻辑，但不再让 host 直接把它当 runtime contract 使用。
- 在 `secnano/main.py` 只接入最小的 trace emit 与 runtime adapter 调用，不做大面积搬迁。

**Acceptance**

- 能构造一个 `TraceEvent` 并同时写入内存 ring buffer 与 SQLite `trace_events` 表。
- 能从 runtime adapter v1 接收 `AgentInput`，返回 `AgentOutput`，且不破坏现有 subprocess 路径。
- 新测试不依赖日志文本，只断言结构字段与持久化结果。

### Priority 2. 在三条黄金路径补稳定事件点

**目标**

- 让普通消息流、主组注册流、定时任务流都产生文档中定义的最小稳定事件集
- 将当前“日志阶段名”和“CI 事件阶段名”对齐

**Files**

- Modify: `secnano/main.py`
- Modify: `secnano/task_scheduler.py`
- Modify: `secnano/ipc.py`
- Modify: `secnano/trace.py`
- Test: `tests/test_message_flow.py`
- Test: `tests/test_ipc_register_flow.py`
- Test: `tests/test_scheduled_task_flow.py`

**Planned Changes**

- 在 `_handle_new_message()` 附近发出 `message.received / stored / group_matched / trigger_miss / no_registered_group / enqueued`。
- 在 `_handle_ipc_task()` 附近发出 `ipc_task.received / auth_checked / rejected / group_registered`，并把当前 `stage="completed"` 收敛为稳定事件名。
- 在 `_enqueue_due_tasks_once()`、`_run_task()`、`_handle_scheduled_task()` 附近发出 `scheduled_task.due / enqueued / started / completed / failed / logged`。
- 在 `_process_group_messages()` 与 runtime adapter 回调处发出 `agent_run.started / prompt_prepared / output_received / reply_sent / completed / failed`。
- `secnano/ipc.py` 仅保留读取和标准化，不承担 Trace 业务规则之外的额外判断。

**Acceptance**

- 三条黄金路径都能查询到稳定 stage 名，不再依赖 structlog event 文案。
- 关键不变量可直接基于事件与 DB 断言：
  - 未注册群不会进入 `agent_run.started`
  - 非主组不会产出 `ipc_task.group_registered`
  - 同一到期任务不会重复 `scheduled_task.started`

### Priority 3. 对 `main.py` 做第一轮最小拆分

**目标**

- 只拆 message ingress、IPC task control plane、runtime orchestration
- `main.py` 保留启动装配、依赖连接、生命周期管理

**Files**

- Create: `secnano/ingress.py`
- Create: `secnano/control_plane.py`
- Create: `secnano/runtime_orchestration.py`
- Modify: `secnano/main.py`
- Test: `tests/test_devplan_d0.py`

**Planned Changes**

- 把 `_handle_new_message()` / `_handle_chat_metadata()` 迁到 `secnano/ingress.py`，只保留解析、存储、入队与事件发射。
- 把 `_handle_ipc_task()` 迁到 `secnano/control_plane.py`，集中主组鉴权和 group 注册控制面。
- 把 `_process_group_messages()`、`_handle_scheduled_task()` 中的 runtime 调用拼装迁到 `secnano/runtime_orchestration.py`。
- `main.py` 改成 wiring 层：初始化 DB、trace store、runtime adapter、channels、scheduler、IPC watcher。

**Acceptance**

- `main.py` 的核心业务函数数量显著下降，只剩启动/装配/生命周期职责。
- 拆分后不新增 channel、swarm、容器增强、复杂 UI 等越界能力。
- 现有 D0 骨架测试保持通过，且新测试仍能跑通同样黄金路径。

### Priority 4. 处理第一轮必须去噪的 A 类遗留代码

**目标**

- 只清理会误导后续开发的代码，不做全仓库整洁化

**Files**

- Modify: `secnano/main.py`
- Modify: `secnano/logger.py`
- Modify: `docs/plans/2026-03-30-ai-execution-instructions.md`

**Planned Changes**

- 明确标注或逐步替换 `main.py` 中基于 `_RECENT_EVENTS` + `_recent_agent_runs` 拼装的 timeline/ops trace 视图，避免被误当成正式 TraceEvent 系统继续复用。
- 若保留 `logger.py` 的 recent event ring buffer，则把它定位为“调试/ops 日志视图”，而不是 CI trace source。
- 把第一轮暂不处理的 B/C 类遗留点记录到文档，不在本轮顺手展开。

**Acceptance**

- 后续开发者阅读主入口时，不会把调试 timeline 误认为 TraceEvent 正式实现。
- 计划与文档里明确哪些旧结构仍存在但不可作为正式 contract 使用。

## Verification Commands

目标命令：

```powershell
.venv\Scripts\python.exe -m pytest tests\test_trace_events.py -q
.venv\Scripts\python.exe -m pytest tests\test_message_flow.py tests\test_ipc_register_flow.py tests\test_scheduled_task_flow.py -q
.venv\Scripts\python.exe -m pytest tests\test_devplan_d0.py -q
```

当前环境前置条件：

- 需要先在 `.venv` 中安装 `dev` 依赖；当前环境尚未安装 `pytest` / `ruff`

## Out of Scope for Round 1

- 新 channel 扩展
- 容器隔离增强
- swarm / 子代理
- 复杂 UI / 监控平台
- 顺手增加额外 feature
- 一次性大重构
