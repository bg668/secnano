# Task Plan

## Goal
围绕 secnano 当前定位，按照 `docs/plans/2026-03-30-constraints-trace-design.md` 与 `docs/plans/2026-03-30-ai-execution-instructions.md` 的固定约束，推进 host orchestrator 第一轮实施计划，并以“小步可验证”的方式准备后续落地。

## Phases
| Phase | Status | Notes |
|---|---|---|
| 1. 建立上下文并识别主链路 | completed | 已阅读约束文档、planning files、主入口、IPC、调度、运行时、日志、测试 |
| 2. 识别第一轮切入点与 A 类遗留代码 | completed | 已确认 `main.py` 过重、Trace 仍依赖 recent log、runtime contract 尚未统一 |
| 3. 产出第一轮实施计划 | completed | 已生成 `docs/plans/2026-03-30-host-orchestrator-round1-implementation-plan.md` 并整理为可执行优先级清单 |
| 4. 第一批底座实施：TraceEvent + runtime contract | completed | 已按 TDD 新增 `TraceEvent`/`AgentInput`/`AgentOutput`、`TraceStore`、`SubprocessRuntimeAdapter`，并通过目标测试 |
| 5. 第二批主链路接入：消息流 + IPC 注册流 | completed | `main.py` 已接入 `_trace_store` 与 runtime adapter，普通消息流/主组注册流已产生稳定 TraceEvent 并通过测试 |
| 6. 第三批黄金路径补齐：定时任务流 | completed | scheduler 已发出 `scheduled_task.due/enqueued/started/completed|failed/logged`，三条黄金路径均已有稳定事件断言 |
| 7. 第四批渐进拆分：ingress + control plane | completed | 已新增 `secnano/ingress.py` 与 `secnano/control_plane.py`，`main.py` 改为薄包装调用，黄金路径测试保持通过 |
| 8. 第五批渐进拆分：runtime orchestration + A类去噪注释 | completed | 已新增 `secnano/runtime_orchestration.py` 并让 `main.py` 通过 orchestrator 薄包装调用，同时明确 recent log 仅用于 ops/debug 视图 |
| 9. 第六批 A类去噪收尾：ops view 外提与死辅助函数移除 | completed | 已新增 `secnano/ops_view.py`，`main.py` 只保留 ops 数据采集与薄包装调用，并删除本地未使用的 ops helper |

## Evaluation Angles
- 产品定位是否收敛在 orchestrator，而不是扩展成泛平台
- 主流程是否形成可用闭环，而不是局部能力拼接
- 模块边界是否支持后续接入不同 agent / CLI
- 当前测试和验证是否足够支撑“能跑”与“能演进”
- 第一轮是否优先落在 runtime contract、TraceEvent、黄金路径测试
- 是否先处理会误导后续开发的 A 类遗留代码，而不是做全仓库清理

## Errors Encountered
| Error | Attempt | Resolution |
|---|---|---|
| `planning-with-files` 的 `session-catchup.py` 无法运行，环境缺少 `python` 命令 | 1 | 记录环境限制，改为手工阅读已有 planning files |
| `uv run pytest -q` 无法执行 | 1 | 当前环境缺少 `pytest` 可执行文件，结论中明确说明验证限制 |
| `uv run ruff check` 无法执行 | 1 | 当前环境缺少 `ruff` 可执行文件，结论中明确说明验证限制 |
