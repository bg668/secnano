**D0（必须完成，先打通主流程）**

| 步骤 | 改造项 | 主要文件 | 完成标准 |
|---|---|---|---|
| 1 | 建立“消息+群元数据”双入库链路：新增 `chat metadata` 入口，不只消息 | [main.py](/D:/Work/01_processing/secnano/secnano/main.py), [ipc.py](/D:/Work/01_processing/secnano/secnano/ipc.py), [db.py](/D:/Work/01_processing/secnano/secnano/db.py), [types.py](/D:/Work/01_processing/secnano/secnano/types.py) | channel 上报消息和群元数据都能入库，且不触发自动注册 |
| 2 | 在 agent 侧暴露 `register_group` 工具（LLM 可调用），并写入 IPC 请求文件 | [tools.py](/D:/Work/01_processing/secnano/agent_runner/tools.py), [main.py](/D:/Work/01_processing/secnano/agent_runner/main.py), [subprocess_runner.py](/D:/Work/01_processing/secnano/secnano/subprocess_runner.py) | 主组 agent 可输出结构化工具调用（工具名+参数） |
| 3 | host 接入 `on_task`，实现 IPC 任务处理与鉴权：`register_group` 必须主组可用、非主组拦截 | [main.py](/D:/Work/01_processing/secnano/secnano/main.py), [ipc.py](/D:/Work/01_processing/secnano/secnano/ipc.py), [db.py](/D:/Work/01_processing/secnano/secnano/db.py) | 非主组调用 `register_group` 被拒；主组通过后写入 `registered_groups` |
| 4 | 调度器改为“到期任务入队”而非直接并发跑，复刻编排语义 | [task_scheduler.py](/D:/Work/01_processing/secnano/secnano/task_scheduler.py), [group_queue.py](/D:/Work/01_processing/secnano/secnano/group_queue.py), [main.py](/D:/Work/01_processing/secnano/secnano/main.py) | 到期任务进入队列执行，避免同组任务并发踩踏 |
| 5 | host 按任务目标群组拉起 agent 执行（已部分存在），补齐状态更新与错误处理闭环 | [main.py](/D:/Work/01_processing/secnano/secnano/main.py), [task_scheduler.py](/D:/Work/01_processing/secnano/secnano/task_scheduler.py), [db.py](/D:/Work/01_processing/secnano/secnano/db.py) | 任务执行、结果落库、next_run/状态更新完整闭环 |

---

**D1（对齐 nanoclaw 控制面能力）**

| 改造项 | 主要文件 | 完成标准 |
|---|---|---|
| 增加任务管理工具：`schedule_task/list_tasks/pause/resume/cancel/update` | [tools.py](/D:/Work/01_processing/secnano/agent_runner/tools.py), [ipc.py](/D:/Work/01_processing/secnano/secnano/ipc.py), [task_scheduler.py](/D:/Work/01_processing/secnano/secnano/task_scheduler.py), [db.py](/D:/Work/01_processing/secnano/secnano/db.py) | 主组可跨组管理任务，非主组仅能管理本组 |
| 输出 `available_groups` 快照给主组 agent（用于“先看可用群，再注册”） | [main.py](/D:/Work/01_processing/secnano/secnano/main.py), [subprocess_runner.py](/D:/Work/01_processing/secnano/secnano/subprocess_runner.py) | 主组可读到候选群列表，非主组不可见全部 |
| 注册模型与路由键对齐：建议引入 `jid` 主键（兼容迁移） | [types.py](/D:/Work/01_processing/secnano/secnano/types.py), [db.py](/D:/Work/01_processing/secnano/secnano/db.py), [main.py](/D:/Work/01_processing/secnano/secnano/main.py) | 注册、匹配、发送链路以 `chat_jid` 稳定运行 |

---

**D2（可选：subagent 能力）**

| 改造项 | 主要文件 | 完成标准 |
|---|---|---|
| 增加“可选子代理”执行开关（默认单 agent），不影响主闭环 | [agent_runner/main.py](/D:/Work/01_processing/secnano/agent_runner/main.py) | 任务可在单 agent 完成；配置开启后可委派子代理 |

---

**测试清单（必须）**

1. 主组 `register_group` 成功，非主组同请求被拒。  
2. 未注册群消息只入库不触发 agent。  
3. 注册后同群消息可被路由并执行。  
4. 到期任务被轮询发现后进入队列执行，不重复触发。  
5. 任务执行失败/成功都写 `task_run_logs`，并正确更新 `next_run/status`。  
6. 并发压测下同组不并发执行、跨组受全局并发限制。

如果你要，我可以下一步直接按这个清单从 D0 开始逐文件落地实现。