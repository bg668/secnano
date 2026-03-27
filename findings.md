# Findings

## Context
- 待核对模块已定位到 `secnano/main.py`、`secnano/ipc.py`、`secnano/db.py`、`secnano/router.py`、`secnano/group_queue.py`、`secnano/channels/registry.py`、`secnano/types.py`。

## Discoveries
- `start_ipc_watcher()` 会在每轮轮询里通过 `_discover_group_folders()` 取 `seed_groups` 与 `data/ipc/*` 目录名并集，符合用户描述。
- watcher 当前扫描顺序是每个组目录下依次 `messages -> tasks -> chat_metadata`，与用户描述中的 `messages -> chat_metadata -> tasks` 不一致。
- `messages/*.json` 中若 `type == "chat_metadata"`，会直接分流为 `ChatMetadata` 处理；`chat_metadata/*.json` 也会走同一类处理器。
- `tasks/*.json` 被解析为 `IpcTaskRequest` 时，`source_group` 来自 `path.parent.parent.name`，即文件路径反推，而不是 JSON 字段。
- secnano 的 `registered_groups` 表以 `folder` 为主键，仅存 `trigger`，没有单独保存目标 `jid`；消息路由时也是遍历组并判断 `g.trigger == new_msg.chat_jid`，发送时 `_process_group_messages()` 又把 `group.trigger` 当成 `chat_jid` 使用。
- nanoclaw 的 `registered_groups` 表则以 `jid` 为主键，`trigger_pattern` 独立存储；运行时 `registeredGroups[chatJid]` 直接按 JID 路由，触发词只参与 `TRIGGER_PATTERN` 判定。
- secnano `_process_group_messages()` 每次固定 `get_messages(chat_jid, limit=50)`，没有读取或更新任何“已处理消息游标”；虽然 DB 有 `router_state` 表，但消息链路未使用它。
- nanoclaw 明确维护 `last_timestamp` 和 `last_agent_timestamp` 两级游标，并通过 `getMessagesSince()` 拉取增量消息，必要时还能在错误场景回滚游标。
- secnano 的 `register_group` 鉴权是 `get_registered_group(task.source_group)` 且必须 `is_main=true`。由于生产代码里没有发现任何初始化 main 组的入口，`is_main=True` 的写入目前只出现在测试里，因此首次冷启动时确实可能进入“能轮询、不能完成授权闭环”的状态。

## Implementation Outcome
- 已在隔离 worktree 中完成改造：`registered_groups` 现在以 `jid` 为一等字段，消息路由按 `jid` 命中、触发词继续独立保留。
- 已新增基于 `router_state` 的 `last_agent_timestamp:{chat_jid}` 游标，`_process_group_messages()` 改为只拉取自上次成功处理后的增量非 bot 消息。
- 已新增 `bootstrap_main_group_if_missing()`，启动时若无 main 组会尝试基于现有 chat metadata / IPC 文件创建主组，打通首次运行授权闭环。
- 在 worktree 中新增 7 条相关回归测试，当前 `uv run pytest -q` 为 9/9 通过，`uv run ruff check` 通过。
