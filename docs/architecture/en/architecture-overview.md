# Architecture V2 — Design Reference

## 1. Purpose of This Document

This document freezes the reference architecture for the `architecture-v2` branch.

**The `architecture-v2` branch starts with design and documentation only.**
No production code is migrated or rewritten in this phase.
Reusable implementation code will be copied over module-by-module in later phases, guided by this document and `../../mapping/main-to-v2-mapping.md`.

This document answers:

1. What the V2 architecture goals are and why the design changed.
2. What the new modules are and what each one is responsible for.
3. How the new modules map to the previous seven core modules.
4. How `nanobot`, `pyclaw`, and `nanoclaw` fit (or don't fit) under the new design.

---

## 2. V2 Goals and Branch Purpose

### 2.1 Why a New Architecture Branch?

The current `main` implementation has accumulated several design compromises:

- **Cognition is coupled to `nanobot`**: The `runtime_bridge.py` shim wraps `nanobot.agent.loop.AgentLoop` directly, making it hard to replace or test the reasoning layer independently.
- **Business logic and LLM interaction logic are mixed**: Orchestration decisions (which role, which backend) and prompt assembly (what to say to the model) are not clearly separated.
- **Agent frameworks treated as infrastructure**: The current design inherits `nanobot`'s config paths, CLI assembly, and session conventions, making `secnano` dependent on upstream choices it should not own.
- **No formal ingress parsing layer**: Raw CLI strings enter the system without a dedicated parsing/validation stage before reaching the orchestrator.
- **No formal output guard**: Model output flows directly to the I/O layer without an explicit validation or safety-check boundary.

### 2.2 V2 Design Goals

1. **High cohesion, low coupling**: Each module owns a single well-defined responsibility. Modules interact through explicit data contracts, not shared internal state or direct imports of each other's internals.
2. **Dependency inversion**: High-level orchestration policy does not depend on low-level execution or provider implementations. Both depend on shared abstract contracts.
3. **Separate business logic from LLM interaction logic**: The orchestrator decides *what* to do; the cognition core decides *how* to reason about it. Neither owns the other's concerns.
4. **Treat agent frameworks as libraries, not as frameworks**: `nanobot` (and any future agent SDK) is called as a library from inside the cognition module. It does not own config paths, CLI assembly, or session management.
5. **Embrace standard protocols and provider abstraction**: LLM providers, execution backends, and capability adapters are all reached through stable internal interfaces. Swapping any one does not cascade changes across the system.
6. **Design before implementation**: On this branch, architecture is frozen in documents first. Code follows documents, not the other way around.

---

## 3. Design Principles in Detail

### 3.1 Single Controller

The system exposes exactly **one main controller agent** (the Zhongshu Sheng) to the outside world.
The controller is **LLM-driven** — it reasons, maintains memory, and uses skills to make scheduling decisions. It is not a deterministic rule engine.
Role execution containers in the Six Ministries are dispatched by that controller — they are not parallel agents.
All new capabilities must be registered through the capability adapter layer and remain subordinate to the single controller.

When a session already has an active execution container, the controller routes requests to that container first to preserve execution context continuity. Container re-assignment only happens on failure, timeout, or explicit policy.

### 3.2 Stable Data Contracts

Every module boundary is expressed as a set of data structures.
When a module produces output, it produces one of the agreed contract types.
When a module consumes input, it consumes one of the agreed contract types.
No module reaches into another module's internal state.

### 3.3 Ephemeral Execution, Persistent Assets

Three objects span different time horizons:

- **Roles** are permanent responsibility definitions. They survive indefinitely across all sessions and container instances.
- **Containers** are short-lived runtime execution instances. They are resource-constrained and recyclable. They do not outlive their work.
- **Sessions** are medium-term task continuity objects. They are more stable than a single container but more concrete than a role definition. A session binds to a container while it is active; the binding can migrate if necessary.

Role assets (SOUL, ROLE, MEMORY, skills, POLICY) and task archives are the long-lived continuity of the system. Containers hold only temporary runtime state; all persistent state must be written back to the Archive & State module before a container is recycled.

### 3.4 Architecture Topology: Court and Government

The V2 architecture uses an expanded court-and-government metaphor.
Each V2 component corresponds to a historical Chinese administrative institution.
This naming scheme is used in all V2 design documents.

---

## 4. The New V2 Architecture: Court and Government Modules

### 4.1 Overview

```
External World
      │
      ▼
┌─────────────────────────────────┐
│  通政司 (Tongzhengsi)            │  ← Ingress / Input Parser
│  Receives, validates, and        │
│  normalises all incoming input   │
└────────────────┬────────────────┘
                 │  InboundEvent
                 ▼
┌──────────────────────────────────────────────────────────┐
│  中书省 (Zhongshu Sheng)  — LLM-driven Controller + Brain │
│  • Owns global context, session state, system-level rules │
│  • Decides: reply directly / follow-up / delegate         │
│  • Has own memory, skills, and controller-level tools     │
│  • Routes requests to session-bound containers (IPC)      │
└──┬────────────────┬─────────────────────┬────────────────┘
   │ queries        │ IPC ExecutionRequest │ archives
   ▼                ▼                     ▼
┌──────────┐  ┌──────────────────────┐  ┌────────────────┐
│ 翰林院   │  │  六部 (Liubu)         │  │ 档案 / Archive │
│ 史馆     │  │  Role Execution Units │  │ Task Records   │
│ RAG +    │  │  ┌─────────────────┐ │  │ + State        │
│ Memory   │  │  │ Container A     │ │  └────────────────┘
└──────────┘  │  │ (Role: X) [LLM] │ │
              │  └─────────────────┘ │
              │  ┌─────────────────┐ │
              │  │ Container B     │ │
              │  │ (Role: Y) [LLM] │ │
              │  └─────────────────┘ │
              │  max-N active slots  │
              └──────────┬───────────┘
                         │ ExecutionResult
                         ▼
┌─────────────────────────────────┐
│  门下省 (Menxia Sheng)           │  ← Validator / Output Guard
│  Validates, filters, and        │
│  approves output before release │
└────────────────┬────────────────┘
                 │  Approved Reply
                 ▼
            External World
```

### 4.2 奏折 / 数据模型 — Memorial / Data Schema

**Historical reference**: In imperial China the *zòuzhé* (奏折, memorial) was the standard form used to communicate between officials and the throne. Every request arrived and departed in a known, structured format.

**Role in V2**:

This is the **shared data contract layer** — the internal language of the system. It is not a runtime module; it is a set of immutable data schemas that every other module depends on.

Key schemas:

| Schema | Description |
|--------|-------------|
| `InboundEvent` | Raw normalised input from Tongzhengsi |
| `Task` | A unit of work dispatched by the orchestrator |
| `ExecutionRequest` | A concrete request sent to the Six Ministries |
| `ExecutionResult` | The result returned from execution |
| `Reply` | The final structured response sent to the user |
| `TaskArchiveRecord` | A persisted record of a completed task |
| `SessionState` | Resumable orchestrator session data, including the current bound `ContainerRecord` |
| `ContainerRecord` | Identity, role binding, lifecycle state, and IPC address of a running container |
| `RoleSpec` | A role's assets: SOUL, ROLE, MEMORY, skills, POLICY |
| `CapabilityDescriptor` | A registered capability's identity and interface contract |

Design rules:

- All schemas are **immutable value objects** (no methods, no logic).
- Every module boundary crossing uses one of these types.
- No module invents ad-hoc dicts or strings as cross-module data.

**Relationship to previous modules**:  
Replaces and expands the *任务/消息模型模块* (Task/Message Model Module, Module 2) from the original seven-module design.

---

### 4.3 通政司 (Tongzhengsi) — Ingress / Input Parser

**Historical reference**: The *Tongzhengsi* (通政司, Office of Transmission) was responsible for receiving and routing all memorials, petitions, and reports before they reached the throne. It ensured nothing malformed entered the imperial decision chain.

**Role in V2**:

This module sits at the system boundary and is the **only entry point** for external input. It:

- Receives raw input from CLI, API, channel, or any other external source.
- Validates and normalises input into a well-typed `InboundEvent`.
- Rejects or quarantines malformed input before it can reach the orchestrator.
- Performs no business logic, no model calls, no role selection.

Inputs:

- Raw CLI arguments / HTTP request body / channel message payload

Outputs:

- `InboundEvent` (on success)
- Structured error response (on validation failure)

Constraints:

- Must not call the LLM.
- Must not make orchestration decisions.
- Must not reach into role assets or archives.

**Relationship to previous modules**:  
Replaces part of the *输入输出模块* (I/O Module, Module 1) from the original design. In V2 the ingress parsing is promoted to a first-class module with a formal validation gate.

---

### 4.4 中书省 (Zhongshu Sheng) — Controller + Brain

**Historical reference**: The *Zhongshu Sheng* (中书省, Secretariat) was the supreme executive organ of the imperial court. It drafted edicts, coordinated the six ministries, and translated imperial will into concrete orders.

**Role in V2**:

The Zhongshu Sheng is the **only externally-facing main controller agent** in the system. It is simultaneously the global scheduling hub and the primary reasoning brain. It is LLM-driven — meaning the controller itself is powered by a language model and is not a deterministic rule engine.

#### 4.4.1 Responsibilities

- Receives all `InboundEvent` objects from Tongzhengsi and performs task understanding.
- Maintains the controller's global context, session state, and system-level rules.
- Makes scheduling decisions based on task type, role capabilities, historical state, and current context.
- Decides whether a task should be:
  - Handled directly with a reply.
  - Followed up with a clarifying question.
  - Delegated to a specific execution container in the Six Ministries.
- Tracks task status, receives `ExecutionResult` objects, and decides whether to continue delegating, terminate, or assemble a final reply.

#### 4.4.2 Capabilities

The Zhongshu Sheng is not a stateless dispatcher. It has:

- **Own memory module**: Stores system-level long-term rules, cross-task experience, scheduling history, and necessary summaries. This is the controller's memory — distinct from role memories managed in the Hanlin/Shiguan layer.
- **Own skill set**: Skills used to perform task decomposition, role selection, status checking, result acceptance, and re-delegation decisions.
- **Controller-level tools**: Tools available to the main controller for orchestration purposes (e.g., inspect session state, query archive, check container availability).

#### 4.4.3 Session Routing Principle

The Zhongshu Sheng applies the following routing principle for session-bearing requests:

- For requests that already have an active `Session`, the controller **should preferentially route the task to the container currently bound to that session**.
- This preserves execution context continuity and avoids the state loss, memory fragmentation, and execution drift that result from frequently switching containers.
- The controller **only re-assigns a new container** for a session when:
  - The original container has failed, been recycled, or timed out.
  - The original container is resource-constrained.
  - Policy explicitly requires migration to a different container.

When a re-assignment is necessary, the controller recovers the necessary context from the Archive & State module before binding the session to the new container.

#### 4.4.4 Boundaries

- The Zhongshu Sheng is responsible for **global scheduling and delegation decisions**.
- It does **not** directly carry out the concrete execution steps inside the Six Ministries.
- It does **not** intervene in the container-internal step-level scheduling, tool selection order, or intermediate execution details.
- Once a task enters an execution container, the specific execution process is completed by the role official running inside that container.

**Relationship to previous modules**:  
Merges and refines the *编排调度模块* (Orchestration Module, Module 3) and *认知内核模块* (Cognition Core Module, Module 4) from the original seven-module design. V2 makes the LLM-driven nature of the controller explicit, adds the session routing principle, and draws a clear boundary between what the controller decides and what the container executes.

---

### 4.5 翰林院 / 史馆 (Hanlin Academy / Shiguan) — RAG + Long-term Memory

**Historical reference**: The *Hanlin Academy* (翰林院) was the imperial academy of scholars responsible for drafting documents, preserving institutional knowledge, and advising on precedent. The *Shiguan* (史馆, Office of History) was the bureau that kept official historical records.

**Role in V2**:

This module provides the system's **retrieval and long-term memory layer**:

- Stores and retrieves role memories and promoted insights.
- Provides RAG (Retrieval-Augmented Generation) index over archived task records, role knowledge bases, and documents.
- Exposes a query interface used by the Zhongshu Sheng cognition sub-layer to enrich prompts with relevant historical context.

Inputs:

- Queries from the cognition sub-layer: "What do I know about X?"
- Memory promotion requests from the orchestrator: "Promote this insight to role Y's long-term memory."

Outputs:

- Retrieved context snippets (for RAG injection into prompts).
- Confirmation of memory promotion.

Design rules:

- The memory layer does not make orchestration decisions.
- Memory promotion goes through an explicit rule-based filter before writing to long-term memory.
- Raw execution results are **not** written directly to long-term memory.

**Relationship to previous modules**:  
Extracts and formalises the memory and retrieval concerns that were scattered across the *角色与能力资产模块* (Roles Module, Module 5) and *归档与状态模块* (Archive Module, Module 7) in the original design.

---

### 4.6 六部 (Liubu) — Six Ministries / Role Execution System

**Historical reference**: The *Liubu* (六部, Six Ministries) were the executive branches of imperial government: Personnel, Revenue, Rites, War, Justice, and Works. Each ministry had specific officials who carried out concrete government work.

**Role in V2**:

The Six Ministries are the system's **role execution system**. The execution officials inside the Six Ministries are not static role definitions — they are **role execution instances** that mount role assets and run inside isolated containers.

#### 4.6.1 Responsibilities

- Accept tasks delegated by the Zhongshu Sheng.
- Complete task refinement, step planning, tool invocation, and result production inside an isolated execution environment.
- Maintain the local execution context and continue processing subsequent commands from the same `Session`.
- Write back execution results, artifact indexes, state summaries, and memory promotion candidates after task completion.

#### 4.6.2 Execution Entity Definition

The "officials" in the Six Ministries are **runtime container instances**, not abstract role files.

- Each execution container, when started, **must mount the role assets** of its assigned role.
- Role assets include at minimum: responsibility description, prompt, long-term memory, skills, policy, tool permissions, and the necessary working directory.
- A container is not a simple command-execution sandbox — it is the **runtime carrier for a role execution official**, with its own LLM, tools, memory, and local state.

#### 4.6.3 Container-Internal Execution Principle

Once a task enters a container, **the specific execution process is completed by the LLM running inside the container**.

The container-internal LLM is responsible for:

- Task refinement
- Step planning
- Tool invocation
- Intermediate result judgment
- Result generation and artifact production

The external controller (Zhongshu Sheng) is only responsible for: "**whether to delegate, to whom, and what resource bounds apply**".

The container interior is responsible for: "**how specifically to complete the task**".

#### 4.6.4 Parallel Control

The parallel capacity of the Six Ministries execution system is controlled by the **maximum number of active containers**:

- Each active container represents one available execution official seat.
- The system can set a global container limit or a per-role container limit to control the concurrent execution scale at any moment.
- Tasks that exceed the limit should enter a waiting, queued, or deferred scheduling state — not trigger unbounded container expansion.

#### 4.6.5 Communication and Lifecycle

- Execution containers communicate with the external system through **IPC**.
- IPC is used to: receive new tasks, respond to status queries, receive supplementary context, handle interrupt signals, and receive termination commands.
- Containers should be treated as **persistently interactive execution units**, not one-shot script processes.
- The same container can continue processing subsequent tasks in the same `Session` throughout its lifecycle.
- A container should be recycled when: the task is complete, the container exits voluntarily, or the container has been inactive for an extended period.
- **Before recycling, a container must write back**: necessary state summaries, key artifact indexes, execution results, and memory promotion candidates to the Archive & State module.

Sub-components:

| Sub-component | Responsibility |
|---------------|---------------|
| Container Backend | Role container lifecycle: start, mount assets, IPC, recycle |
| Host Backend | Direct in-process execution (for lightweight tasks) |
| Tool Registry | Tool definitions, execution dispatch, permission enforcement |
| Artifact Manager | Workspace mounting, artifact collection, result packaging |

#### 4.6.6 Boundaries

- The Six Ministries execution system is responsible for execution — not for global scheduling.
- Execution containers are **not** exposed directly as new user-facing entry points.
- All Six Ministries officials must serve the unified scheduling of the Zhongshu Sheng and must not form a parallel second control system.

**Relationship to previous modules**:  
Corresponds to the *执行模块* (Execution Module, Module 6) and *工具注册模块* (Tool Registry Module) from the original design. V2 makes explicit that containers are LLM-driven role execution instances (not simple command runners), adds the parallel control mechanism, and formalises the IPC-based lifecycle.

---

### 4.7 门下省 (Menxia Sheng) — Validator / Output Guard

**Historical reference**: The *Menxia Sheng* (门下省, Chancellery) was the review body that could examine and return (refuse to countersign) edicts drafted by the Secretariat before they took effect. It was an explicit check on what left the top of government.

**Role in V2**:

This module is the **output validation and safety gate**:

- Receives draft `Reply` objects from the Zhongshu Sheng.
- Applies policy rules, safety filters, and format validation.
- Either approves and passes the reply to the I/O layer, or rejects and returns a structured refusal.

Inputs:

- Draft `Reply` from the Zhongshu Sheng.
- Policy configuration from role assets and platform rules.

Outputs:

- Approved `Reply` (to I/O output layer).
- Structured rejection (back to Zhongshu Sheng for revision or escalation).

Design rules:

- The Menxia Sheng does not generate content. It only reviews.
- Policy rules are declarative and do not embed LLM calls.
- The output guard runs **after** cognition is complete and **before** the reply is sent to the user.

**Relationship to previous modules**:  
This is a **new formal module** in V2. In the original seven-module design, output validation was implicit (part of the I/O module or the orchestrator). V2 makes it an explicit, testable boundary.

---

### 4.8 Role / Container / Session — Three-Layer Relationship

`Role`, `Container`, and `Session` represent three distinct levels of object. They must be strictly differentiated.

#### 4.8.1 Role

A `Role` is a **static role definition** representing the responsibility boundary and capability profile of an execution official.

Contents:

- Responsibility description
- Prompt
- Long-term memory
- Skills
- Tool permissions
- Resource scope
- Security policy

Constraints:

- A `Role` is not a runtime instance.
- The same `Role` can be reused by multiple execution containers.
- A `Role` is a long-term stable responsibility identity — it does not directly equal any specific execution run.

#### 4.8.2 Container

A `Container` is the **runtime instantiation carrier** of a `Role`. It is the dynamic execution entity that actually accepts tasks and maintains local execution context.

Characteristics:

- A `Container` mounts the assets of its assigned `Role` at startup.
- A `Container` holds its runtime context, temporary state, and execution artifacts throughout its lifecycle.
- A `Container` is resource-constrained and recyclable — it is not a permanent identity.
- A `Container` is the actual execution official instance that completes tasks.

Constraints:

- One `Container` belongs to exactly one `Role`.
- One `Role` can correspond to multiple `Container` instances.
- A `Container` is a short-lived execution instance and must not be treated as a permanent identity object.

#### 4.8.3 Session

A `Session` is the **logical identity of task continuity**, used to ensure that multiple rounds of requests belong to the same work chain logically.

Characteristics:

- A `Session` represents the context continuum of a segment of continuous task processing.
- A `Session` is not directly equal to a `Role`.
- A `Session` is not directly equal to a `Container`.
- A `Session` is maintained by the Zhongshu Sheng and used to route multi-round requests to the appropriate execution context.

Default binding:

- An active `Session` should preferentially be bound to one specific `Container` at any given moment.
- Subsequent requests under the same `Session` should, in principle, continue to be sent to the currently bound `Container`.
- This binding maintains task context, local memory, and the continuity of in-progress execution state.

Migration rules:

- When the original `Container` fails, is recycled, times out, or is no longer suitable for the current task, the Zhongshu Sheng may re-assign a new `Container` for the `Session`.
- During re-assignment, necessary context should be restored through the Archive & State module.
- After re-assignment, the original `Role` may continue to be used, or a new `Role` may be selected based on task changes.

Long-term vs. short-term boundary:

| Object | Nature | Stability |
|--------|--------|-----------|
| `Role` | Long-term stable responsibility identity | Permanent — survives across all sessions and containers |
| `Container` | Short-lived runtime execution instance | Ephemeral — recycled when idle or done |
| `Session` | Task continuity object between the two | Medium-term — more stable than a single container, more concrete than a role definition |

---

## 5. Supporting Infrastructure Modules

The following infrastructure modules support the court modules above.
They are carry-overs from the original twelve-module design with minor refinements:

| Module | V2 Role | Notes |
|--------|---------|-------|
| Configuration Management | Owns all config: providers, roles, execution, archive | Must not couple to `nanobot.config.*` |
| AI Provider Module | Abstracts LLM vendor access | Called only from Zhongshu Sheng cognition sub-layer |
| Skill Registry | Discovers and loads skills; generates skill summaries | Maintains `SKILL.md` compatibility |
| Capability Adapter | Translates external capabilities into internal `CapabilityDescriptor` | Entry point for `nanobot`, `pyclaw`, `nanoclaw`, and future adapters |
| Archive / State | Persists `TaskArchiveRecord`, `SessionState`, artifact indexes | Feeds into the Hanlin/Shiguan retrieval layer |

---

## 6. Module Summary Table

| V2 Module | Chinese Name | Analogy | Replaces / Adds |
|-----------|-------------|---------|----------------|
| Data Schema | 奏折 / 数据模型 | Memorial format | Replaces Module 2 (expands scope) |
| Tongzhengsi | 通政司 | Office of Transmission | Replaces I/O ingress half of Module 1 |
| Zhongshu Sheng | 中书省 | Secretariat | Merges + refines Modules 3 & 4 |
| Hanlin / Shiguan | 翰林院 / 史馆 | Academy + History Office | Extracts memory/RAG from Modules 5 & 7 |
| Liubu | 六部 | Six Ministries | Unifies Modules 6 + Tool Registry |
| Menxia Sheng | 门下省 | Chancellery | **New** — formally adds output guard |
| I/O Output | (Output of Module 1) | Imperial Proclamation | Retains output half of Module 1 |

---

## 7. Relationship to `nanobot`, `pyclaw`, and `nanoclaw`

### 7.1 `nanobot`

Under V2 architecture, `nanobot` is treated as an **optional library**, not as a host framework.

- The Zhongshu Sheng cognition sub-layer **may** call `nanobot.agent.loop.AgentLoop` as a library, wrapped behind a stable internal interface.
- No other module may import or depend on `nanobot` internals.
- `nanobot.config.*`, `nanobot.cli.*`, `nanobot.channels.*`, and `~/.nanobot` conventions are explicitly **out of scope** for V2.
- `packages/nanobot/` in the repository serves as the compatibility shim location. Its scope is strictly limited to the cognition sub-layer shim.

### 7.2 `pyclaw` (`refs/pyclaw`)

`pyclaw` is a **reference implementation** for the container runtime and IPC protocol.

- The Liubu (Six Ministries) container backend should follow the protocols defined in `refs/pyclaw`.
- No production code is copied wholesale; instead, the protocols are studied and implemented natively in V2.

### 7.3 `nanoclaw` (`refs/nanoclaw`)

`nanoclaw` is a **reference implementation** of container orchestration in TypeScript.

- It provides architectural reference for container lifecycle, group queue, task scheduler, and IPC.
- `refs/nanoclaw/docs/` contains additional architecture documents that may inform V2 container design.
- As with `pyclaw`, it is reference material only; code is not imported.

### 7.4 Summary

| Component | V2 Treatment |
|-----------|-------------|
| `nanobot` runtime loop | Library shim inside Zhongshu Sheng cognition sub-layer only |
| `nanobot` config / CLI / channels | **Excluded** from V2 |
| `refs/pyclaw` | Protocol reference for Liubu container backend |
| `refs/nanoclaw` | Architecture reference for Liubu container orchestration |
| `packages/nanobot/` | Shim location for cognition-only compatibility |

---

## 8. What `architecture-v2` Does and Does Not Do

### This Branch Does

- Freeze the reference architecture in documents.
- Define module boundaries, data contracts, and dependency rules.
- Map current code to the new architecture (see `../../mapping/main-to-v2-mapping.md`).
- Plan a staged implementation approach (see `../../plan/roadmap.md`).

### This Branch Does Not

- Bulk-port the existing `secnano/` implementation.
- Rewrite `runtime_bridge.py` or any other production file.
- Migrate `nanobot` integration wholesale.
- Lock in a single agent framework before the cognition interface is stable.
- Change the `main` branch.

---

## 9. Relationship to Previous Seven Core Modules

| Original Module (main) | Status in V2 | V2 Destination |
|------------------------|-------------|----------------|
| 1. I/O Module | Split | Ingress half → Tongzhengsi; Output half → I/O Output layer |
| 2. Task/Message Model | Promoted | → Data Schema (奏折), expanded scope |
| 3. Orchestration Module | Refined | → Zhongshu Sheng orchestration sub-layer |
| 4. Cognition Core Module | Refined | → Zhongshu Sheng cognition sub-layer |
| 5. Roles & Assets Module | Refined | Assets remain; memory/RAG extracted → Hanlin/Shiguan |
| 6. Execution Module | Unified | → Liubu (Six Ministries), merged with tool registry |
| 7. Archive & State Module | Refined | Archive remains; retrieval surface feeds Hanlin/Shiguan |
| Tool Registry (support) | Absorbed | → Part of Liubu |
| Skill Registry (support) | Retained | Unchanged role, now feeds Zhongshu Sheng explicitly |
| Capability Adapter (support) | Retained | Entry point for all external capabilities |
| Config Management (support) | Retained | Stricter `nanobot` decoupling |
| AI Provider (support) | Retained | Called only from cognition sub-layer |

---

## 10. Next Steps

This document is the starting point. The recommended next documents and actions are:

1. **`docs/mapping/main-to-v2-mapping.md`** — Map every current file/area to a V2 module. Classify as: keep, migrate, redesign, split, merge, or deprecate.
2. **`docs/plan/roadmap.md`** — Define the phase-by-phase implementation roadmap.
3. (Later) Begin Phase 1 implementation: data schema definitions, Tongzhengsi skeleton, Menxia Sheng skeleton.
