# Roadmap Phase 0~5 完成度对照表（逐条映射到文件与测试）

> 用途：可直接复制到 PR 描述中，说明 roadmap 各阶段交付物与仓库内证据（实现文件、测试、验证命令）的对应关系。

---

## 1) 总览

| Phase | 目标 | 当前状态 | 证据入口 |
|---|---|---|---|
| Phase 0 | 架构冻结 | 已完成 | `docs/architecture/*`、`docs/mapping/*`、`docs/plan/roadmap*.md` |
| Phase 1 | Schema + 主链路骨架 | 已完成（已由真实实现覆盖） | `src/v2/schemas/*`、`src/v2/__main__.py`、`tests/v2/test_schemas.py` |
| Phase 2 | 入口 + 归档 | 已完成 | `src/v2/tongzhengsi/*`、`src/v2/archive/*`、`src/v2/roles/loader.py`、`tests/v2/test_integration_chain.py` |
| Phase 3 | 六部 Host 执行 | 已完成 | `src/v2/liubu/*`、`tests/v2/test_integration_chain.py`（execution 字段断言） |
| Phase 4 | 中书省认知 + Provider | 已完成 | `src/v2/zhongshu/*`、`src/v2/providers/*`、`src/v2/hanlin/retriever.py` |
| Phase 5 | 门下省守卫 + 集成 | 已完成 | `src/v2/menxia/*`、`src/v2/__main__.py`（统一 guard 入口）、`python -m secnano_v2 self-test --chain` |

---

## 2) 分阶段逐条映射

### Phase 0：Architecture Freeze

| Roadmap 交付物 | 已落地文件 |
|---|---|
| 架构总览文档 | `docs/architecture/en/architecture-overview.md`、`docs/architecture/zh/architecture-overview.md` |
| main → v2 映射文档 | `docs/mapping/main-to-v2-mapping.md`、`docs/mapping/main-to-v2-mapping.zh-CN.md` |
| roadmap 文档 | `docs/plan/roadmap.md`、`docs/plan/roadmap.zh-CN.md` |

验证方式：文档审阅（无需运行代码）。

---

### Phase 1：Schemas + Main Chain Skeleton

| Roadmap 交付物 | 已落地文件 | 测试 / 验证 |
|---|---|---|
| `InboundEvent` | `src/v2/schemas/inbound.py` | `tests/v2/test_schemas.py`（冻结不可变） |
| `Task` / `ExecutionRequest` / `ExecutionResult` | `src/v2/schemas/task.py` | 主链路集成验证（见下方命令） |
| `Reply` | `src/v2/schemas/reply.py` | 主链路集成验证 |
| `TaskArchiveRecord` | `src/v2/schemas/archive.py` | `tests/v2/test_integration_chain.py`（归档 JSON 校验） |
| `RoleSpec` | `src/v2/schemas/roles.py` | `tests/v2/test_integration_chain.py`（角色路径） |
| `CognitionRequest` / `CognitionResult` | `src/v2/schemas/cognition.py` | 主链路集成验证 |
| 主链路入口连通 | `src/v2/__main__.py`、`secnano_v2/__main__.py` | `python -m secnano_v2 delegate --role demo --task "hello"` |
| Hanlin mock（固定返回空） | `src/v2/hanlin/retriever.py` | 代码审查可见 `query -> []` |

---

### Phase 2：Ingress + Archive

| Roadmap 交付物 | 已落地文件 | 测试 / 验证 |
|---|---|---|
| 真实 CLI 入站构建 + 校验 | `src/v2/tongzhengsi/cli_channel.py`、`src/v2/tongzhengsi/validator.py` | `tests/v2/test_integration_chain.py` |
| 结构化 ingress 错误 | `src/v2/tongzhengsi/errors.py` | `test_missing_role_is_structured_error`（无 traceback） |
| 归档写入 | `src/v2/archive/writer.py` | `test_delegate_writes_archive_and_prints_reply` |
| 归档读取接口 | `src/v2/archive/reader.py` | 手工验证：读取 `runtime/tasks/*.json` |
| 角色资产加载 | `src/v2/roles/loader.py`、`roles/demo/{SOUL,ROLE,MEMORY,POLICY}` | `test_missing_role_is_structured_error` |

验证命令：

```bash
python -m secnano_v2 delegate --role demo --task "write a hello world"
python -m secnano_v2 delegate --role missing --task "hello"
```

---

### Phase 3：Execution (Liubu Host)

| Roadmap 交付物 | 已落地文件 | 测试 / 验证 |
|---|---|---|
| `ExecutionBackend` 协议 | `src/v2/liubu/backends/base.py` | 编排调用链使用 host backend |
| Host backend | `src/v2/liubu/backends/host.py` | `test_delegate_writes_archive_and_prints_reply` |
| 工具注册与调度 | `src/v2/liubu/tools/registry.py`、`src/v2/liubu/tools/specs.py` | `delegate --task "run echo hello"` 触发 `echo` |
| 归档持久化执行结果 | `src/v2/archive/writer.py` + `TaskArchiveRecord.execution` | 集成测试断言 `record["execution"]["tool_name"] == "echo"` |

验证命令：

```bash
python -m secnano_v2 delegate --role demo --task "run echo hello"
```

---

### Phase 4：Cognition (Zhongshu Sheng)

| Roadmap 交付物 | 已落地文件 | 测试 / 验证 |
|---|---|---|
| Provider 协议 | `src/v2/providers/base.py`（`AIProvider`） | 主链路集成验证 |
| OpenAI provider 示例 | `src/v2/providers/openai.py` | 手工验证（需要 `OPENAI_API_KEY`） |
| Prompt 组装 | `src/v2/zhongshu/cognition/prompting.py` | 主链路集成验证 |
| Cognition runtime | `src/v2/zhongshu/cognition/runtime.py` | `delegate` 过程中生成 `CognitionResult` |
| Orchestrator 串联 cognition→execution | `src/v2/zhongshu/orchestrator.py` | `test_delegate_writes_archive_and_prints_reply` |
| nanobot 可选隔离层 | `src/v2/zhongshu/cognition/nanobot_shim.py` | 代码结构审查 |
| Hanlin mock-only 规则 | `src/v2/hanlin/retriever.py` | 代码审查可见固定 `[]` |

验证命令：

```bash
python -m secnano_v2 delegate --role demo --task "summarise this"
# 如需真实 provider：
# export SECNANO_PROVIDER=openai
# export OPENAI_API_KEY=...
# python -m secnano_v2 delegate --role demo --task "say hello in three languages"
```

---

### Phase 5：Output Guard + Integration

| Roadmap 交付物 | 已落地文件 | 测试 / 验证 |
|---|---|---|
| Guard 主体（Reply → ApprovedReply / Rejection） | `src/v2/menxia/guard.py` | `src/v2/__main__.py` 统一调用 `OutputGuard().inspect(...)` |
| Policy 协议 | `src/v2/menxia/policies/base.py` | 代码结构审查 |
| Format policy | `src/v2/menxia/policies/format.py` | 主链路集成验证（非空回复可通过） |
| Safety policy | `src/v2/menxia/policies/safety.py` | 主链路集成验证 |
| E2E 集成 | `src/v2/__main__.py`、`tests/v2/test_integration_chain.py` | `python -m secnano_v2 self-test --chain` |

验证命令：

```bash
python -m secnano_v2 delegate --role demo --task "hello"
python -m secnano_v2 self-test --chain
```

---

## 3) 当前可复用验证命令（可直接贴 PR）

```bash
# 单元 + 集成
python -m unittest discover -s tests -q

# 主链路
python -m secnano_v2 delegate --role demo --task "run echo hello"
python -m secnano_v2 self-test --chain

# 结构化错误路径
python -m secnano_v2 delegate --role missing --task "hello"
```
