# 迁移计划 V2

> **注**：本文件是 [`roadmap.md`](./roadmap.md) 的中文译本，内容保持同步。

## 1. 文档目的

本文档定义了从当前仅含设计的 `architecture-v2` 分支过渡到可工作的 V2 实现的分阶段计划。

配套阅读：

- `docs/architecture/zh/architecture-overview.md` — V2 架构规范参考
- `docs/mapping/main-to-v2-mapping.zh-CN.md` — 当前模块到 V2 模块的映射与操作分类

---

## 2. 指导原则

### 2.1 Agent 守则

以下守则在每个阶段无一例外地适用：

- **围绕主链路做最小闭环，不做孤立模块** — 不构建无法端到端验证的孤立模块。
- **框架优先，业务只做样例** — 结构和契约先于实际逻辑；实际逻辑在后续阶段逐步引入。
- **stub/mock 必须守正式接口，不能乱写占位** — 占位实现必须与真实实现遵循相同的类型和签名。
- **每次交付必须可运行、可观察、可验收，并附验证命令** — 每个阶段提供验证命令，用于演练当前主链路。
- **角色只做最小职责，RAG 只做 mock** — 翰林院/史馆层在整个核心阶段保持为接口兼容的 mock；真实检索引擎是可选的未来扩展。
- **refs/ 只参考，不直接整体复制** — 不从 `refs/pyclaw` 或 `refs/nanoclaw` 整体复制；学习并重新实现。

### 2.2 主链路

每个阶段都要保持以下链路端到端可运行。从 Phase 1 起，每个节点以 stub 或真实实现的形式存在——从不缺席：

```
CLI → InboundEvent → Orchestrator → Cognition → ExecutionRequest
    → Host Backend → ExecutionResult → Archive → Reply → Guard → CLI Output

Phase 1：所有节点为接口兼容的 stub
Phase 2：CLI 和 Archive 替换为真实实现
Phase 3：Host Backend 替换为真实实现
Phase 4：Orchestrator 和 Cognition 替换为真实实现
Phase 5：Guard 替换为真实实现
```

### 2.3 非目标

- 不批量移植现有 `secnano/` 实现。整体复制会带入 V2 旨在修复的设计妥协。
- 在认知接口稳定之前，不过早锁定单一 Agent 框架。
- 不修改 `main` 作为 V2 工作的一部分。
- 不将 `refs/pyclaw` 或 `refs/nanoclaw` 的代码作为生产代码导入。

---

## 3. 阶段总览

| 阶段 | 名称 | 目标 | 先决条件 |
|------|------|------|---------|
| 0 | 架构冻结 | 设计文档完成并达成共识 | — |
| 1 | Schema + 主链路骨架 | 最小契约定义完毕；全链路以 stub 可运行 | Phase 0 |
| 2 | 入口 + 归档 | 真实 CLI 解析和真实任务持久化 | Phase 1 |
| 3 | 执行（六部 Host） | 真实 host backend + 工具注册表 | Phase 2 |
| 4 | 认知（中书省） | 真实 LLM 编排 + AI Provider 抽象 | Phase 3 |
| 5 | 输出守卫 + 集成 | 真实门下省校验门；全链路验证 | Phase 4 |

容器 backend（完整 LLM 驱动的容器生命周期）是 **Phase 5 之后的扩展**，延后至主链路稳定且确认需要容器执行后再实施。

---

## 4. Phase 0：架构冻结

**状态**：已完成。

**目标**：完成并达成 V2 架构设计文档共识。

**交付物**：

- [x] `docs/architecture/zh/architecture-overview.md` — V2 模块定义、设计原则、朝廷隐喻
- [x] `docs/mapping/main-to-v2-mapping.zh-CN.md` — 当前到 V2 的映射与操作分类
- [x] `docs/plan/roadmap.zh-CN.md` — 本文档

**完成标准**：

- 三份文档均在 `architecture-v2` 分支上并经过审查。
- 模块边界、数据契约和依赖规则已达成共识。
- 没有修改任何实现代码。

---

## 5. Phase 1：Schema + 主链路骨架

**目标**：定义主链路所需的最小契约类型，然后以接口兼容的 stub 连通每个模块，使链路从第一次提交起就能端到端运行。

**交付物**：

Schema（仅契约——不含业务逻辑）：

- `src/v2/schemas/inbound.py` — `InboundEvent`
- `src/v2/schemas/task.py` — `Task`、`ExecutionRequest`、`ExecutionResult`
- `src/v2/schemas/reply.py` — `Reply`
- `src/v2/schemas/archive.py` — `TaskArchiveRecord`
- `src/v2/schemas/roles.py` — `RoleSpec`
- `src/v2/schemas/cognition.py` — `CognitionRequest`、`CognitionResult`

Stub（接口兼容，不是随意占位字符串）：

- `src/v2/tongzhengsi/cli_channel.py` — stub：从 argv 读取 `--role` 和 `--task`，返回硬编码 `InboundEvent`
- `src/v2/zhongshu/orchestrator.py` — stub：接收 `InboundEvent`，返回硬编码 `ExecutionRequest` 和 `Reply`
- `src/v2/zhongshu/cognition/stub.py` — stub：`CognitionRequest` → 固定 `CognitionResult`
- `src/v2/liubu/backends/host.py` — stub：`ExecutionRequest` → 固定 `ExecutionResult`
- `src/v2/hanlin/retriever.py` — mock（核心阶段 1–5 全程保持 mock）：`query(str) → []`；真实检索是 Phase 6+ 的可选扩展，遵循 Agent 守则
- `src/v2/archive/writer.py` — stub：将 `TaskArchiveRecord` 写为 JSON 文件至 `runtime/tasks/`
- `src/v2/menxia/guard.py` — stub：原样通过任何 `Reply`
- `src/v2/__main__.py` — 入口：将所有 stub 连通为主链路

测试：

- 单元测试：schema 构造、字段类型、冻结不可变性。
- 冒烟测试：全链路 stub 运行产出 `Reply` 并生成归档文件。

**设计规则**：

- 每个 stub 必须导入并实例化它所产出的 schema 类型——不使用裸 dict 或无类型字符串。
- 翰林院 mock 返回空列表，在核心阶段不替换（RAG 只做 mock）。
- 编排器 stub 必须按顺序调用认知 stub 和 host backend stub，从第一天起链路结构就是正确的。

**完成标准**：

- `python -m secnano_v2 delegate --role demo --task "hello"` 向 stdout 打印回复，并写入 JSON 归档文件。
- 单元测试通过。

**验证命令**：

```bash
python -m secnano_v2 delegate --role demo --task "hello"
# 预期：打印 Reply 内容；生成 runtime/tasks/<task_id>.json
```

---

## 6. Phase 2：入口 + 归档

**目标**：用真实 CLI 解析替换通政司 stub，用真实文件持久化替换归档 stub。

**交付物**：

- `src/v2/tongzhengsi/cli_channel.py` — 真实 CLI 参数解析器，产出经校验的 `InboundEvent`
- `src/v2/tongzhengsi/validator.py` — 输入校验与规范化
- `src/v2/tongzhengsi/errors.py` — 结构化入口错误类型
- `src/v2/archive/writer.py` — 真实 `TaskArchiveRecord` 持久化（JSON 文件写入 `runtime/tasks/`）
- `src/v2/archive/reader.py` — 归档查询读接口
- `src/v2/roles/loader.py` — 角色资产加载（`SOUL`、`ROLE`、`MEMORY`、`POLICY` 文件 → `RoleSpec`）

测试：

- 有效 CLI 输入 → `InboundEvent`；格式不合规输入 → 结构化错误，而非堆栈跟踪。
- 归档往返：写入后读回相同的 `TaskArchiveRecord`。
- 角色加载器：缺少必要文件时抛出结构化错误。

**来源映射**：从 `secnano/cli.py`、`archive.py`、`roles.py` 重新设计。

**完成标准**：

- `python -m secnano_v2 delegate --role <role> --task "<task>"` 产出有效 `InboundEvent` 并持久化 `TaskArchiveRecord`。
- `python -m secnano_v2 delegate --role missing` 以结构化错误退出，不产生堆栈跟踪。

**验证命令**：

```bash
python -m secnano_v2 delegate --role demo --task "write a hello world"
cat runtime/tasks/*.json          # 归档文件存在且为有效 JSON

python -m secnano_v2 delegate     # 缺少必填参数
# 预期：结构化错误，退出码 != 0
```

---

## 7. Phase 3：执行（六部 Host Backend）

**目标**：用真实执行 backend 替换 host backend stub，使其能够执行任务并返回结构化 `ExecutionResult`。

**交付物**：

- `src/v2/liubu/backends/base.py` — `ExecutionBackend` 协议
- `src/v2/liubu/backends/host.py` — 真实 host 执行 backend
- `src/v2/liubu/tools/registry.py` — 工具定义和调度
- `src/v2/liubu/tools/specs.py` — 工具 schema 类型
- `src/v2/archive/writer.py` — 扩展：在 `TaskArchiveRecord` 旁边持久化 `ExecutionResult`

测试：

- Host backend 接收 `ExecutionRequest`，运行一个简单工具，返回 `ExecutionResult`。
- 工具注册表列出并调度内置工具。
- `ExecutionResult` 持久化到归档。

**来源映射**：从 `backends/host.py` 迁移；参考 `refs/` 了解工具模式。

**完成标准**：

- 示例执行请求运行内置工具（如 `echo`），输出出现在归档中。
- 编排器 stub 仍通过 `ExecutionBackend` 协议调用 host backend；链路保持可运行。

**验证命令**：

```bash
python -m secnano_v2 delegate --role demo --task "run echo hello"
cat runtime/tasks/*.json          # 归档记录内含 ExecutionResult
```

---

## 8. Phase 4：认知（中书省）

**目标**：用真实 LLM 驱动的编排层替换认知 stub，置于 `CognitionRequest` / `CognitionResult` 契约之后。

**交付物**：

- `src/v2/providers/base.py` — `AIProvider` 协议
- `src/v2/providers/openai.py` — OpenAI Provider（主要样例）
- `src/v2/zhongshu/cognition/runtime.py` — 认知入口点（`CognitionRequest` → `CognitionResult`）
- `src/v2/zhongshu/cognition/prompting.py` — 从 `RoleSpec` + 翰林院 mock 上下文组装提示词
- `src/v2/zhongshu/orchestrator.py` — 真实编排器：`InboundEvent` → 认知 → `ExecutionRequest` → backend → `Reply`
- `src/v2/zhongshu/cognition/nanobot_shim.py` — **可选**垫片，如仍使用 `nanobot` 则仅在此处隔离

测试：

- 从 `RoleSpec` 加上空翰林院上下文组装提示词，产出非空提示字符串。
- Provider 协议：mock provider 返回 `CognitionResult`；仅通过配置切换到真实 provider。
- 集成：`InboundEvent` → 编排器 → 认知 → `ExecutionRequest` → host backend → `Reply`。

**设计规则**：

- `nanobot`（如使用）只从 `nanobot_shim.py` 调用，其他文件不导入。
- 翰林院 mock 继续返回空列表；提示词仅从角色资产组装上下文。

**完成标准**：

- `python -m secnano_v2 delegate --role demo --task "summarise this"` 调用真实 LLM 并返回连贯回复。
- 切换 Provider（OpenAI → Anthropic）只需修改配置键，无需改代码。

**验证命令**：

```bash
export SECNANO_PROVIDER=openai
python -m secnano_v2 delegate --role demo --task "say hello in three languages"
# 预期：打印真实 LLM 回复；归档含 CognitionResult
```

---

## 9. Phase 5：输出守卫 + 集成

**目标**：用真实基于策略的校验门替换门下省 stub，并验证所有真实模块的完整主链路端到端。

**交付物**：

- `src/v2/menxia/guard.py` — 真实输出守卫（`Reply` → `ApprovedReply | Rejection`）
- `src/v2/menxia/policies/base.py` — 策略规则协议
- `src/v2/menxia/policies/format.py` — 格式校验（非空、有效 UTF-8、长度限制）
- `src/v2/menxia/policies/safety.py` — 内容安全规则（初始宽松；按角色收紧）
- 端到端集成测试：CLI → `InboundEvent` → 编排器 → 认知 → 执行 → 守卫 → 回复。

测试：

- 已审批的回复原样通过。
- 违反格式策略的回复产出结构化 `Rejection`，而非原始模型字符串。
- `Rejection` 反馈给编排器（不直接打印给用户）。

**设计规则**：

- 守卫不生成内容——只检查并审批或拒绝。
- 策略规则是声明式的，不调用 LLM。

**完成标准**：

- 每条回复路径在到达 CLI 输出之前都经过守卫。
- 故意构造的格式违规回复（如通过测试注入）被捕获并产出 `Rejection`。
- 完整端到端集成测试通过。

**验证命令**：

```bash
python -m secnano_v2 delegate --role demo --task "hello"
# 预期：打印已审批回复；归档含 ApprovedReply 记录

python -m secnano_v2 self-test --chain
# 预期：运行全链路冒烟测试；所有步骤通过
```

---

## 10. 迁移阶段汇总

| 阶段 | 关键模块 | 来源 | 主链路状态 |
|------|---------|------|----------|
| 0 | 文档 | — | 不适用 |
| 1 | Schema + 全部 stub | 新建 | **可运行（全 stub）** |
| 2 | 通政司 + 归档 | `cli.py`、`archive.py` → 重新设计 | 可运行（真实入口 + 归档） |
| 3 | 六部 Host Backend | `backends/host.py` → 迁移 | 可运行（真实执行） |
| 4 | 中书省认知 + Provider | `runtime_bridge.py` → 重新设计 | 可运行（真实 LLM） |
| 5 | 门下省守卫 + 集成 | 新建 | **全真实** |

---

## 11. V2 实现建议目录结构

```
src/
  v2/
    schemas/                    ← Phase 1：数据契约（不可变）
      inbound.py
      task.py
      reply.py
      archive.py
      roles.py
      cognition.py
    tongzhengsi/                ← Phase 2：入口（CLI → InboundEvent）
      cli_channel.py
      validator.py
      errors.py
    archive/                    ← Phase 2：持久化
      writer.py
      reader.py
    roles/                      ← Phase 2：角色资产加载
      loader.py
    liubu/                      ← Phase 3：执行
      backends/
        base.py
        host.py
      tools/
        registry.py
        specs.py
    providers/                  ← Phase 4：AI Provider 抽象
      base.py
      openai.py
    zhongshu/                   ← Phase 4：编排器 + 认知
      orchestrator.py
      cognition/
        runtime.py
        prompting.py
        nanobot_shim.py         ← 可选；隔离 nanobot 依赖
    hanlin/                     ← 全程 mock
      retriever.py              ← 核心阶段永久返回 []
    menxia/                     ← Phase 5：输出守卫
      guard.py
      policies/
        base.py
        format.py
        safety.py
    __main__.py                 ← Phase 1：连通主链路的入口
tests/
scripts/
docs/
refs/                           ← 仅保留轻量级参考索引
```

> **容器 backend**（`liubu/backends/container.py` 及 `liubu/container/`）：延后至 Phase 6+。仅在 host backend 主链路完全稳定且确认需要容器执行时再添加。
