# 模块边界清单

## 1. 文档目的

本文档定义当前建议采用的系统模块边界。

重点回答三类问题：

1. 每个模块各自负责什么。
2. 每个模块的输入、输出和边界是什么。
3. 模块之间的数据如何流转，以及哪些模块应该脱离 `nanobot`、哪些只应参考 `nanoclaw/pyclaw`、哪些只能保留临时兼容层。

说明：

- 本文档只讨论核心业务与基础支撑模块。
- 默认不把安全治理单独展开；安全策略后续挂接在执行模块、角色模块和归档模块上。
- 本文档替代此前分散的路线、原则、目标架构、实施计划类文档。

## 2. 总体分层

当前建议把系统分成两组模块：

### 2.1 核心业务模块

1. 输入输出模块
2. 任务/消息模型模块
3. 编排调度模块
4. 认知内核模块
5. 角色与能力资产模块
6. 执行模块
7. 归档与状态模块

### 2.2 基础支撑模块

1. 配置管理模块
2. AI 供应商模块
3. 工具注册模块
4. 技能注册/加载模块
5. 能力适配模块

### 2.3 核心架构硬约束

1. 系统对外只有一个主控 agent。
2. 角色执行单元只是被主控 agent 调度的“官员实例”，不是多个平行对外 agent。
3. 所有新能力必须通过适配模块挂接到现有主控 agent，而不是额外创建第二套总控流。
4. 执行实例是临时的，角色资产和历史归档才是长期连续体。

用朝廷类比表示：

- 外部输入输出模块 = 皇帝和外界接口
- 编排调度模块 + 认知内核模块 = 宰相中枢
- 角色与能力资产模块 = 官职档案与职权定义
- 执行模块 = 官员办事场所
- 归档与状态模块 = 书库与案卷系统

## 3. 模块边界

### 3.1 输入输出模块

职责：

- 接收 CLI、外部 app、后续 channel 或 API 请求
- 输出最终结果、状态信息、错误信息
- 不直接承载任务理解、角色选择、执行细节

输入：

- 原始用户输入
- 外部附件引用
- 状态查询请求
- 编排调度模块返回的最终回复

输出：

- 标准化前的原始事件
- 面向外部的最终结果
- 运行状态与进度反馈

边界：

- 只负责边界通信
- 不允许直接调用执行模块
- 不允许直接构造角色、容器、工具实例

上游策略：

- 建议完全从 `nanobot` 脱离
- 不再继续耦合 `nanobot/cli/`
- 不再继续耦合 `nanobot/channels/`

### 3.2 任务/消息模型模块

职责：

- 把外部输入统一成标准数据结构
- 作为全系统内部公共语言
- 保存任务、消息、附件、回复、执行请求的标准模型

输入：

- 输入输出模块提供的原始请求
- 编排调度模块补充的上下文、session、角色、执行标记

输出：

- `InboundEvent`
- `Task`
- `Reply`
- `ExecutionRequest`
- `ExecutionResult`
- `AttachmentRef`

边界：

- 只定义和转换数据结构
- 不负责调度决策
- 不负责模型调用
- 不负责容器执行

上游策略：

- 建议完全从 `nanobot` 脱离
- 不把 `nanobot.bus.events` 当作系统标准模型

### 3.3 编排调度模块

职责：

- 管理 session 和任务状态
- 判断直接回答还是拆解子任务
- 选择角色、构造委派任务
- 决定走宿主执行还是容器执行
- 验收结果并汇总最终回复

输入：

- 标准化后的 `Task`
- 角色与能力资产模块提供的角色资产
- 归档与状态模块提供的历史状态
- 认知内核模块提供的理解、总结和中间结果
- 执行模块返回的 `ExecutionResult`

输出：

- 直接回复请求
- 子任务委派请求
- 容器执行请求
- 归档写入请求
- 对输入输出模块的最终 `Reply`

边界：

- 负责决策，不负责执行落地
- 不直接管理容器生命周期细节
- 不直接持有 provider 或 tool 的底层实现

上游策略：

- 建议完全从 `nanobot` 脱离
- 不再继续耦合 `nanobot.agent.subagent`
- 不再继续耦合 `nanobot.agent.tools.spawn`

### 3.4 认知内核模块

职责：

- 组装 prompt 和上下文
- 执行多轮模型调用
- 处理 tool calling 回路
- 生成中间思考、阶段结论和最终自然语言结果

输入：

- 编排调度模块提交的认知请求
- 角色模块提供的角色提示词、记忆、技能摘要
- 工具注册模块提供的工具定义
- AI 供应商模块提供的模型访问能力

输出：

- 自然语言结论
- 工具调用请求
- 结构化执行建议
- 用于归档的原始模型输出

边界：

- 只负责认知和工具调用回路
- 不负责外部 I/O
- 不负责角色治理
- 不负责容器与工件落盘

上游策略：

- 短期可保留兼容层
- 可以暂时通过 `secnano` 本地接口包装 `nanobot.agent.loop.AgentLoop`
- 但必须隔离在一个内部适配接口后

绝对不要继续耦合：

- `nanobot.cli.commands` 的私有装配逻辑
- `nanobot.config.*` 的路径与配置语义
- `~/.nanobot` 目录假设

### 3.5 角色与能力资产模块

职责：

- 提供角色定义
- 提供角色提示词、记忆、技能、工具权限、资源范围
- 作为编排调度与执行的静态资产来源

输入：

- 角色定义文件
- `SOUL.md`
- `ROLE.md`
- 角色记忆文件
- 技能目录
- 策略与权限配置
- 共享规则文件

输出：

- `RoleSpec`
- 角色 SOUL
- 角色 prompt
- 角色长期记忆
- 角色允许的工具、挂载和执行限制

边界：

- 提供静态或半静态资产
- 不直接执行任务
- 不直接做调度决策

上游策略：

- 建议完全从 `nanobot` 脱离
- 技能内容格式可兼容 `SKILL.md`
- 角色加载、挂载、分配逻辑由 `secnano` 自己实现

角色资产包建议至少包含：

- `SOUL.md`：角色使命、处事风格、长期身份设定
- `ROLE.md`：职责范围、擅长任务、默认工作方式
- `MEMORY.md`：角色长期记忆
- `skills/`：技能目录
- `POLICY.json` 或等价结构：工具、挂载、写权限、执行限制
- 共享规则引用：平台级公共规则，不允许角色自行改写

建议优先级：

1. 平台共享规则
2. 当前任务的硬约束
3. `SOUL.md`
4. `ROLE.md`
5. `MEMORY.md`
6. `skills/`

执行权限优先级：

1. 系统安全策略
2. 角色权限策略
3. 当前任务临时申请的能力范围

### 3.6 执行模块

职责：

- 按调度请求准备执行环境
- 启动容器或宿主执行单元
- 挂载 workspace、角色资产和工件目录
- 注入 secrets
- 读取输入、运行任务、写回结果

输入：

- 编排调度模块提交的 `ExecutionRequest`
- 角色与能力资产模块提供的角色资源
- 配置模块提供的运行时参数

输出：

- `ExecutionResult`
- 工件目录
- 执行日志
- 归档元数据

边界：

- 只负责执行落地
- 不负责决定执行什么
- 不负责生成最终面对用户的回复

上游策略：

- 主要参考 `nanoclaw/pyclaw`
- 尤其参考容器协议、挂载控制、secrets 注入、IPC 和生命周期管理
- 不建议继续依赖 `nanobot` 的 subagent 设计

### 3.7 归档与状态模块

职责：

- 保存任务归档、工件索引、执行元数据、日志摘要
- 保存 session 状态和可恢复状态
- 为记忆提升、审计、失败恢复提供统一读取面

输入：

- 编排调度模块提交的状态变化
- 执行模块提交的结果与日志
- 认知内核模块提交的原始输出摘要

输出：

- `TaskArchiveRecord`
- `SessionState`
- 工件索引
- 查询接口和历史读取接口

边界：

- 负责保存和读取
- 不直接决定调度路径
- 不直接调用模型或执行容器

上游策略：

- 建议完全从 `nanobot` 脱离
- 不把 `nanobot` 的 session/history 当本系统最终归档模型

### 3.8 配置管理模块

职责：

- 管理本项目自身配置
- 定义运行时、provider、roles、execution、archive 等配置轴

输入：

- 配置文件
- 环境变量
- 启动参数

输出：

- 结构化配置对象
- 运行时路径与策略开关

边界：

- 只负责解析和提供配置
- 不负责执行业务逻辑

上游策略：

- 建议完全从 `nanobot` 脱离
- 不再继续耦合 `nanobot.config.loader`
- 不再继续耦合 `nanobot.config.schema`
- 不再继续耦合 `nanobot.config.paths`

### 3.9 AI 供应商模块

职责：

- 管理模型供应商定义
- 管理 provider 选择、鉴权、模型参数和调用适配

输入：

- 配置管理模块提供的 provider 配置
- 认知内核模块提交的模型调用请求

输出：

- 统一 provider 接口
- 标准化的模型返回对象

边界：

- 只负责模型访问
- 不直接持有业务路由与会话策略

上游策略：

- 建议完全从 `nanobot` 脱离
- 可参考 `nanobot/providers/` 的实现思路
- 不建议长期直接依赖 `nanobot` provider registry

### 3.10 工具注册模块

职责：

- 注册工具定义
- 为认知内核提供稳定的工具清单
- 管理工具执行入口和权限描述

输入：

- 工具实现
- 工具元数据
- 角色允许的工具范围

输出：

- 工具定义列表
- 工具执行分发接口

边界：

- 只负责工具元数据和执行挂接
- 不负责高层业务调度

上游策略：

- 建议在 `secnano` 自己实现
- 可参考 `nanobot` 的 registry 结构
- 不建议长期直接耦合 `nanobot.agent.tools.registry`

### 3.11 技能注册/加载模块

职责：

- 发现技能
- 读取技能说明
- 生成给角色或认知内核使用的技能摘要

输入：

- 技能目录
- `SKILL.md`
- 技能脚本或附属资源

输出：

- 技能索引
- 技能摘要
- 技能挂载信息

边界：

- 只负责技能发现与挂载
- 不负责直接执行整个任务

上游策略：

- 建议由 `secnano` 自己实现
- 保留 `SKILL.md` 兼容
- 不需要继续耦合 `nanobot.agent.skills`

### 3.12 能力适配模块

职责：

- 把外部 agent 或新能力转成系统内部可装载的标准能力
- 屏蔽外部实现差异
- 保证所有新增能力仍服务于单一主控 agent

输入：

- 外部能力实现
- 第三方协议、schema 或运行时
- 本系统定义的适配合同

输出：

- `CapabilityAdapter`
- 可注册的工具定义
- 可注册的执行后端
- 可注册的认知扩展或 provider 扩展

边界：

- 只负责适配，不负责重新定义主流程
- 不允许把外部能力直接暴露成第二个对外 agent
- 不允许绕过任务模型、编排调度和归档链路

上游策略：

- `nanobot`、`nanoclaw/pyclaw` 以及后续第三方能力都应通过这一层接入
- 建议以稳定适配合同而不是直接 import 上游内部文件的方式集成

## 4. 模块之间的数据流转关系

### 4.1 直接回答路径

1. 输入输出模块接收请求
2. 任务/消息模型模块生成标准 `Task`
3. 编排调度模块判断可直接回答
4. 编排调度模块调用认知内核模块
5. 认知内核模块通过 AI 供应商模块完成推理
6. 编排调度模块整理 `Reply`
7. 输入输出模块输出最终结果
8. 归档与状态模块保存过程摘要和结果

### 4.2 角色委派路径

1. 输入输出模块接收请求
2. 任务/消息模型模块生成标准 `Task`
3. 编排调度模块查询角色与能力资产模块
4. 编排调度模块决定拆分子任务
5. 编排调度模块生成 `ExecutionRequest`
6. 执行模块读取角色资产并运行任务
7. 执行模块产出 `ExecutionResult`
8. 编排调度模块验收结果并决定是否追加任务
9. 编排调度模块生成最终 `Reply`
10. 输入输出模块输出最终结果
11. 归档与状态模块保存归档、工件和执行状态

### 4.3 记忆与状态更新路径

1. 归档与状态模块保存任务原始结果
2. 角色与能力资产模块从归档中筛选可提升内容
3. 只有经过提升规则筛选的内容才进入角色长期记忆
4. 主流程只读取必要摘要，不直接把原始执行结果写入长期记忆

### 4.4 外部能力装载路径

1. 能力适配模块读取外部能力定义或运行时
2. 能力适配模块把外部能力翻译为内部 `CapabilityAdapter`
3. 适配结果注册到工具注册模块、执行模块或认知内核模块的适配入口
4. 编排调度模块仍然只面对系统内部合同，不直接感知上游内部实现
5. 所有新增能力最终都由同一个主控 agent 调用，而不是形成新的用户入口

## 5. 允许的依赖方向

建议依赖方向如下：

- 输入输出模块 -> 任务/消息模型模块
- 编排调度模块 -> 任务/消息模型模块、认知内核模块、角色与能力资产模块、执行模块、归档与状态模块
- 认知内核模块 -> AI 供应商模块、工具注册模块、技能注册/加载模块
- 能力适配模块 -> 认知内核模块、执行模块、AI 供应商模块、工具注册模块的适配接口
- 执行模块 -> 配置管理模块、角色与能力资产模块、归档与状态模块
- 角色与能力资产模块 -> 技能注册/加载模块、归档与状态模块

不建议的反向依赖：

- 执行模块 -> 输入输出模块
- 执行模块 -> 编排调度模块内部状态
- 工具注册模块 -> 编排调度模块
- AI 供应商模块 -> 角色模块
- 归档与状态模块 -> 认知内核模块
- 能力适配模块 -> 输入输出模块
- 外部能力运行时 -> 编排调度模块内部状态

## 6. 上游耦合策略总结

### 6.1 建议完全从 `nanobot` 脱离

- 输入输出模块
- 任务/消息模型模块
- 编排调度模块
- 角色与能力资产模块
- 归档与状态模块
- 配置管理模块
- AI 供应商模块
- 工具注册模块
- 技能注册/加载模块
- 能力适配模块

### 6.2 主要参考 `nanoclaw/pyclaw`

- 执行模块
- 容器运行协议
- 挂载控制
- secrets 注入
- IPC 与任务生命周期

### 6.3 暂时保留兼容层

- 认知内核模块

建议方式：

- 通过 `secnano` 自己的 `agent_runtime` 接口包装现有 `nanobot` loop
- 后续逐步替换为本地实现

### 6.4 绝对不要继续耦合上游

- `nanobot.cli.commands` 私有装配逻辑
- `nanobot.config.*` 配置与路径语义
- `nanobot.agent.subagent`
- `nanobot.agent.tools.spawn`
- `nanobot.channels.*`
- `~/.nanobot` 路径约定

## 7. 建议目录结构

```text
secnano/
  secnano/
    io/
      cli/
      api/
      presenters/
    models/
      inbound.py
      task.py
      reply.py
      execution.py
      attachments.py
    orchestrator/
      sessions.py
      router.py
      planner.py
      dispatcher.py
      reviewer.py
    cognition/
      runtime.py
      prompting.py
      loop.py
      tools_bridge.py
    roles/
      models.py
      loader.py
      registry.py
      memory.py
    execution/
      backends/
        host.py
        container.py
      runtime/
        workspace.py
        mounts.py
        secrets.py
        lifecycle.py
      artifacts.py
    archive/
      tasks.py
      sessions.py
      artifacts.py
      queries.py
    config/
      schema.py
      loader.py
      paths.py
    providers/
      base.py
      registry.py
      factory.py
    tools/
      registry.py
      specs.py
      executors/
    skills/
      loader.py
      registry.py
      parser.py
    integrations/
      nanobot/
        agent_runtime.py
      adapters/
        base.py
        registry.py
        capability_specs.py
    governance/
      audit.py
      memory_promotion.py
      role_admin.py
  roles/
    engineering_office/
      SOUL.md
      ROLE.md
      MEMORY.md
      POLICY.json
      skills/
    research_office/
      SOUL.md
      ROLE.md
      MEMORY.md
      POLICY.json
      skills/
  rules/
    PLATFORM.md
  runtime/
    tasks/
    sessions/
    artifacts/
    logs/
  packages/
    nanobot/
  refs/
    pyclaw/
    nanoclaw/
```

## 8. 当前推荐的迁移顺序

1. 先把配置管理、provider、工具注册从 `nanobot` 脱离。
2. 再把认知内核前面的装配逻辑全部收回到 `secnano`。
3. 建立统一 `CapabilityAdapter` 合同，把外部新能力的接入入口固定下来。
4. 容器执行模块继续按 `nanoclaw/pyclaw` 路线补齐真实执行链。
5. 最后再决定认知内核是否彻底替换 `nanobot` loop。
