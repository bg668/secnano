# Architecture V2 — Design Reference

## 1. Purpose of This Document

This document freezes the reference architecture for the `architecture-v2` branch.

**The `architecture-v2` branch starts with design and documentation only.**
No production code is migrated or rewritten in this phase.
Reusable implementation code will be copied over module-by-module in later phases, guided by this document and `module_mapping_v2.md`.

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

The system exposes exactly **one main controller agent** to the outside world.
Roles are temporary execution units dispatched by that controller — they are not parallel agents.
All new capabilities must be registered through the capability adapter layer and remain subordinate to the single controller.

### 3.2 Stable Data Contracts

Every module boundary is expressed as a set of data structures.
When a module produces output, it produces one of the agreed contract types.
When a module consumes input, it consumes one of the agreed contract types.
No module reaches into another module's internal state.

### 3.3 Ephemeral Execution, Persistent Assets

Execution instances (containers, host processes) are temporary.
Role assets (SOUL, ROLE, MEMORY, skills, POLICY) and task archives are the long-lived continuity of the system.

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
┌─────────────────────────────────┐
│  中书省 (Zhongshu Sheng)         │  ← Controller + Brain (Orchestrator + Cognition)
│  Decides what to do;            │
│  assembles prompts; calls model; │
│  dispatches execution           │
└──┬──────────┬──────────┬────────┘
   │          │          │
   │  queries │ dispatches│  archives
   ▼          ▼          ▼
┌──────┐  ┌───────┐  ┌────────────┐
│翰林院 │  │ 六部  │  │奏折 / 档案  │
│史馆  │  │(Liubu)│  │(Archive)   │
│RAG  │  │Exec + │  │Task Records│
│+Mem │  │Tools  │  │+ State     │
└──────┘  └───────┘  └────────────┘
                 │
                 ▼ ExecutionResult
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
| `SessionState` | Resumable orchestrator session data |
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

This is the **central orchestrator and cognition core**, unified into one logical component but split into two sub-layers:

#### 4.4.1 Orchestration Sub-layer (Controller)

Responsibilities:

- Receives `InboundEvent` from Tongzhengsi.
- Manages session state.
- Decides: direct reply, sub-task delegation, or execution request.
- Selects roles and constructs `ExecutionRequest` objects.
- Validates `ExecutionResult` from the Six Ministries.
- Assembles the final `Reply`.

#### 4.4.2 Cognition Sub-layer (Brain)

Responsibilities:

- Assembles prompts from role assets, memory, and task context.
- Executes the multi-turn LLM call loop.
- Manages tool-calling feedback cycles.
- Produces structured intermediate results and natural language conclusions.

Design rules:

- The controller does not import LLM provider internals; it calls the cognition sub-layer through a stable internal interface.
- The cognition sub-layer does not import orchestration state; it receives a self-contained cognition request and returns a cognition result.
- Agent frameworks (`nanobot` or any future SDK) are called **from inside** the cognition sub-layer only, as a library. They do not own any other layer's concerns.

**Relationship to previous modules**:  
Merges and refines the *编排调度模块* (Orchestration Module, Module 3) and *认知内核模块* (Cognition Core Module, Module 4) from the original seven-module design, with clearer internal boundaries.

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

### 4.6 六部 (Liubu) — Six Ministries / Execution + Tools

**Historical reference**: The *Liubu* (六部, Six Ministries) were the executive branches of imperial government: Personnel, Revenue, Rites, War, Justice, and Works. They carried out specific categories of concrete action.

**Role in V2**:

This module is the **execution and tool layer**:

- Receives `ExecutionRequest` from the Zhongshu Sheng.
- Prepares the execution environment (container or host).
- Mounts role assets, workspaces, and artifacts.
- Injects secrets.
- Dispatches tool calls.
- Returns `ExecutionResult`.

Sub-components:

| Sub-component | Responsibility |
|---------------|---------------|
| Host Backend | Direct in-process execution |
| Container Backend | Isolated container execution (references `pyclaw`/`nanoclaw` protocols) |
| Tool Registry | Tool definitions, execution dispatch, permission enforcement |
| Artifact Manager | Workspace mounting, artifact collection, result packaging |

Design rules:

- The Six Ministries receive orders; they do not decide what orders to create.
- They do not call the LLM directly.
- Container protocols and IPC follow the reference designs in `refs/pyclaw` and `refs/nanoclaw`.

**Relationship to previous modules**:  
Corresponds to the *执行模块* (Execution Module, Module 6) and *工具注册模块* (Tool Registry Module) from the original design, now formally unified as a single execution + tools boundary.

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
- Map current code to the new architecture (see `module_mapping_v2.md`).
- Plan a staged implementation approach (see `migration_plan_v2.md`).

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

1. **`docs/module_mapping_v2.md`** — Map every current file/area to a V2 module. Classify as: keep, migrate, redesign, split, merge, or deprecate.
2. **`docs/migration_plan_v2.md`** — Define the phase-by-phase implementation roadmap.
3. (Later) Begin Phase 1 implementation: data schema definitions, Tongzhengsi skeleton, Menxia Sheng skeleton.
