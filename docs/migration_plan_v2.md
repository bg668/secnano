# Migration Plan V2

## 1. Purpose of This Document

This document defines the phased plan for moving from the current design-only `architecture-v2` branch to a working V2 implementation.

Read alongside:

- `docs/architecture_v2.md` — canonical V2 architecture reference
- `docs/module_mapping_v2.md` — current-to-V2 module mapping and action classifications

---

## 2. Governing Principles

Before reading the phases, note the following constraints that apply throughout the migration:

### 2.1 Non-Goals for the Current Phase (Design-Only)

The `architecture-v2` branch is **documentation only** right now. The following are explicitly out of scope until Phase 1 begins:

- **Do not bulk-port the existing `secnano/` implementation**. Copying files wholesale would carry over the design compromises V2 is designed to fix.
- **Do not lock into a single agent framework early**. The Zhongshu Sheng cognition sub-layer interface must be stable before committing to `nanobot` or any replacement.
- **Do not start implementation until the Data Schema (奏折) is agreed**. All other modules depend on the contract types; building them before the schema is settled wastes effort.
- **Do not modify `main`** as part of V2 work. V2 is a clean-design branch; `main` continues on its own milestone track.
- **Do not import from `refs/pyclaw` or `refs/nanoclaw`** as production code. They are reference material only.

### 2.2 Principles That Apply in All Phases

- Every phase produces working, testable artifacts — not just code stubs.
- Every phase maintains the module boundary rules defined in `architecture_v2.md`.
- Each module is implemented behind its contract interface before the next module depends on it.
- The single-controller constraint is enforced from the first integration test onward.

---

## 3. Phases Overview

| Phase | Name | Goal | Prerequisites |
|-------|------|------|--------------|
| 0 | Architecture Freeze | Design documents complete and agreed | — |
| 1 | Data Schema Definition | All V2 contract types defined and validated | Phase 0 |
| 2 | Ingress (Tongzhengsi) | CLI and initial channel adapters produce InboundEvent | Phase 1 |
| 3 | Archive and Roles | Archive, role asset loading, and memory promotion migrated | Phase 1 |
| 4 | RAG and Memory Retrieval | Hanlin/Shiguan retrieval layer operational | Phase 3 |
| 5 | Execution and Tools (Liubu) | Host backend + tool registry working end-to-end | Phases 2 & 3 |
| 6 | Container Backend | Full container lifecycle using pyclaw protocols | Phase 5 |
| 7 | Provider and Cognition | AI provider abstraction + Zhongshu Sheng cognition redesign | Phases 1 & 5 |
| 8 | Output Guard (Menxia Sheng) | Output validation gate integrated into the reply path | Phase 7 |
| 9 | Final Migration and Consolidation | End-to-end V2 pipeline; deprecate main compatibility shims | All phases |

---

## 4. Phase 0: Architecture Freeze

**Status**: In progress (this branch).

**Goal**: Complete and agree on V2 architecture design documents.

**Deliverables**:

- [x] `docs/architecture_v2.md` — V2 module definitions, design principles, court metaphor
- [x] `docs/module_mapping_v2.md` — current-to-V2 mapping with action classifications
- [x] `docs/migration_plan_v2.md` — this document

**Done criteria**:

- All three documents are on the `architecture-v2` branch and reviewed.
- Module boundaries, data contracts, and dependency rules are agreed.
- No implementation code has been changed.

**Non-goals for this phase**:

- No Python files created or modified (except documentation).
- No tests written.
- No CLI changes.

---

## 5. Phase 1: Data Schema Definition

**Goal**: Define all V2 contract types. Every subsequent phase depends on these.

**Deliverables**:

- `v2/schemas/inbound.py` — `InboundEvent`
- `v2/schemas/task.py` — `Task`, `ExecutionRequest`, `ExecutionResult`
- `v2/schemas/reply.py` — `Reply`
- `v2/schemas/archive.py` — `TaskArchiveRecord`, `SessionState` (includes current bound `ContainerRecord` reference)
- `v2/schemas/container.py` — `ContainerRecord` (identity, role binding, lifecycle state, IPC address, max-slot config)
- `v2/schemas/roles.py` — `RoleSpec`
- `v2/schemas/capabilities.py` — `CapabilityDescriptor`
- `v2/schemas/cognition.py` — `CognitionRequest`, `CognitionResult`
- Unit tests validating schema construction, serialisation, and immutability.

**Design rules**:

- All schemas must be immutable value objects (use `@dataclass(frozen=True)` or Pydantic `BaseModel` with `model_config = ConfigDict(frozen=True)`).
- No business logic inside schemas.
- No imports from any V2 module other than sibling schemas.

**Done criteria**:

- All schema files exist with full field definitions.
- Unit tests pass.
- At least one round-trip serialisation test per schema.

---

## 6. Phase 2: Ingress (Tongzhengsi)

**Goal**: Build the Tongzhengsi (通政司) ingress layer. CLI input produces validated `InboundEvent` objects.

**Deliverables**:

- `v2/tongzhengsi/__init__.py`
- `v2/tongzhengsi/cli_channel.py` — CLI argument parser producing `InboundEvent`
- `v2/tongzhengsi/validator.py` — Input validation and normalisation
- `v2/tongzhengsi/errors.py` — Structured ingress error types
- Unit tests for: valid input → `InboundEvent`; invalid input → structured error.

**Source mapping**: Redesign from `secnano/cli.py`.

**Design rules**:

- Tongzhengsi must not call the LLM, load role assets, or reach into the archive.
- Output is always either a valid `InboundEvent` or a structured ingress error.
- Future channels (API, Slack, etc.) are added as additional channel adapters in this module.

**Done criteria**:

- `python -m secnano_v2 delegate --role <role> --task "<task>"` produces a valid `InboundEvent`.
- Malformed input produces a structured error, not a stack trace.

---

## 7. Phase 3: Archive and Roles

**Goal**: Migrate the archive persistence layer and role asset loading into V2.

**Deliverables**:

- `v2/archive/tasks.py` — `TaskArchiveRecord` persistence (JSON or SQLite)
- `v2/archive/sessions.py` — `SessionState` persistence
- `v2/archive/queries.py` — Read interface for archive queries
- `v2/roles/loader.py` — Role asset loading (SOUL, ROLE, MEMORY, skills, POLICY)
- `v2/roles/registry.py` — In-memory role registry
- `v2/roles/memory.py` — Memory promotion with filtering rules
- Unit tests for: archive round-trip; role loading from filesystem; memory promotion rules.

**Source mapping**:

- `archive.py` → `v2/archive/tasks.py` (migrate)
- `roles.py` loader → `v2/roles/loader.py` (migrate)
- `roles.py` promote-memory → `v2/roles/memory.py` (split out)

**Done criteria**:

- Archive records can be written and read using V2 schema types.
- Role assets load from the `roles/` directory into `RoleSpec` objects.
- Memory promotion writes only filtered insights to `MEMORY.md`.

---

## 8. Phase 4: RAG and Memory Retrieval (Hanlin / Shiguan)

**Goal**: Build the Hanlin/Shiguan (翰林院/史馆) retrieval layer that provides context to the cognition sub-layer.

**Deliverables**:

- `v2/hanlin/__init__.py`
- `v2/hanlin/retriever.py` — Query interface over archived records and role memories
- `v2/hanlin/indexer.py` — Index management (simple keyword or embedding-based)
- `v2/hanlin/memory_gate.py` — Promotion filter rules (only filtered insights → long-term memory)
- Unit tests for: retrieval query returns relevant records; promotion gate rejects unfiltered raw output.

**Design rules**:

- The retrieval layer is read-only from the perspective of the cognition sub-layer (it does not write).
- Memory promotion writes only through `memory_gate.py`, never directly.
- Start with simple keyword matching; add embedding-based retrieval in a later iteration.

**Done criteria**:

- Cognition sub-layer can query for relevant context by keyword.
- Memory gate correctly blocks raw execution outputs from reaching long-term memory.

---

## 9. Phase 5: Execution and Tools (Liubu)

**Goal**: Build the Liubu (六部) execution layer with a working host backend and tool registry.

**Deliverables**:

- `v2/liubu/__init__.py`
- `v2/liubu/backends/base.py` — `ExecutionBackend` protocol
- `v2/liubu/backends/host.py` — Host execution backend
- `v2/liubu/tools/registry.py` — Tool definitions and dispatch
- `v2/liubu/tools/specs.py` — Tool schema types
- `v2/liubu/artifacts.py` — Artifact collection and packaging
- Integration tests for: host backend receives `ExecutionRequest`, executes, returns `ExecutionResult`.

**Source mapping**:

- `backends/base.py` → `v2/liubu/backends/base.py` (migrate)
- `backends/host.py` → `v2/liubu/backends/host.py` (migrate)
- `adapters/base.py` → inform `CapabilityDescriptor` in schema + `v2/liubu/backends/base.py`

**Done criteria**:

- Host backend executes a trivial task end-to-end using V2 schema types.
- Tool registry lists and dispatches at least one built-in tool.
- `ExecutionResult` is written to archive after execution.

---

## 10. Phase 6: Container Backend

**Goal**: Implement the full container execution backend, following `refs/pyclaw` protocols. Each container is an LLM-driven role execution instance, not a simple command sandbox.

**Deliverables**:

- `v2/liubu/backends/container.py` — Full container lifecycle management (start, mount, IPC, recycle)
- `v2/liubu/container/workspace.py` — Workspace mounting
- `v2/liubu/container/mounts.py` — Mount control (role assets, skills, artifacts)
- `v2/liubu/container/secrets.py` — Secret injection
- `v2/liubu/container/lifecycle.py` — Container start / monitor / stop / recycle
- `v2/liubu/container/ipc.py` — IPC protocol (following `refs/pyclaw/bus/`): task delivery, status query, supplementary context, interrupt, termination
- `v2/liubu/container/slots.py` — Active container slot management (global limit + per-role limit; queue/wait when limit exceeded)
- `v2/liubu/container/writeback.py` — Pre-recycle state writeback: state summary, artifact indexes, results, memory candidates → Archive & State
- Integration tests requiring a local container runtime.

**Source mapping**:

- `refs/pyclaw/container_runner.py` → Protocol reference only; reimplement natively.
- `refs/pyclaw/bus/` → IPC reference; reimplement natively.
- `backends/pyclaw_container.py` → Discard; replace with redesigned implementation.

**Design rules**:

- The container-internal LLM is responsible for task refinement, step planning, tool invocation, intermediate judgment, and result generation. The Zhongshu Sheng does not intervene in these internal decisions.
- The Zhongshu Sheng communicates with containers via IPC only. IPC messages carry: new task assignments, supplementary context, status queries, interrupt signals, and termination commands.
- A `Session` should be routed to its currently bound `Container` whenever possible. Container slot management must track which session is bound to which container.
- Containers must write back all persistent state before being recycled.

**Done criteria**:

- A task can be delegated to a container backend using V2 schema types.
- The container-internal LLM completes the task and produces an `ExecutionResult` via IPC.
- Session binding is preserved: a subsequent request to the same session routes to the same container.
- When the active container limit is reached, new tasks queue rather than spawning additional containers.
- Secrets are not written to disk outside the container scope.
- Container writeback completes before recycle.

---

## 11. Phase 7: Provider and Cognition (Zhongshu Sheng Brain)

**Goal**: Build the AI provider abstraction and redesign the Zhongshu Sheng cognition sub-layer behind a stable internal interface.

**Deliverables**:

- `v2/providers/base.py` — `AIProvider` protocol
- `v2/providers/registry.py` — Provider registry and selection
- `v2/providers/factory.py` — Provider factory from configuration
- `v2/zhongshu/cognition/runtime.py` — Cognition sub-layer entry point (`CognitionRequest` → `CognitionResult`)
- `v2/zhongshu/cognition/prompting.py` — Prompt assembly from role assets and Hanlin context
- `v2/zhongshu/cognition/loop.py` — Multi-turn LLM call loop with tool-calling feedback
- `v2/zhongshu/cognition/nanobot_shim.py` — **Optional** shim wrapping `nanobot.agent.loop.AgentLoop` behind the interface (if `nanobot` is still in use)
- Unit tests for: prompt assembly from `RoleSpec` + retrieval context; provider abstraction returns standard response.

**Design rules**:

- `nanobot` (if used) is called only from `nanobot_shim.py`. No other file imports `nanobot`.
- The cognition sub-layer interface (`CognitionRequest` / `CognitionResult`) must be stable before `nanobot_shim.py` is replaced with a native implementation.

**Done criteria**:

- A `CognitionRequest` with a role and task produces a `CognitionResult` with a natural language conclusion.
- Swapping the provider (e.g., from OpenAI to Anthropic) requires only a configuration change, not a code change.
- All tool-calling cycles complete within the cognition sub-layer; no tool results leak to the orchestrator as raw strings.

---

## 12. Phase 8: Output Guard (Menxia Sheng)

**Goal**: Implement the Menxia Sheng (门下省) output guard as an explicit validation gate in the reply path.

**Deliverables**:

- `v2/menxia/__init__.py`
- `v2/menxia/guard.py` — Output validation entry point (`Reply` → `ApprovedReply | Rejection`)
- `v2/menxia/policies/base.py` — Policy rule protocol
- `v2/menxia/policies/format.py` — Format validation rules
- `v2/menxia/policies/safety.py` — Content safety rules (initially permissive; tighten per role)
- Unit tests for: approved reply passes through; rejection returns structured error.

**Design rules**:

- The guard does not generate content. It only inspects and approves or rejects.
- Policy rules are declarative and do not call the LLM.
- Rejection feeds back to the Zhongshu Sheng orchestrator, not directly to the user.

**Done criteria**:

- Every reply path in the V2 orchestrator passes through the guard before reaching the I/O output layer.
- A policy violation produces a structured rejection, not a raw model output.

---

## 13. Phase 9: Final Migration and Consolidation

**Goal**: Complete the end-to-end V2 pipeline, deprecate main compatibility shims, and validate the full architecture.

**Deliverables**:

- `v2/zhongshu/orchestrator/` — Full orchestration sub-layer (sessions, planner, dispatcher, reviewer)
- End-to-end integration tests: CLI input → InboundEvent → orchestrator → cognition → execution → output guard → reply.
- Deprecation of `packages/nanobot/nanobot_shim.py` (or replace with native loop if `nanobot` is no longer needed).
- Updated `docs/project_progress.md` (V2 section) with completion status.
- Decision record: retain `nanobot` as library shim or replace with native cognition loop.

**Done criteria**:

- A full delegate task (role selection → cognition → execution → archive → reply) completes using only V2 modules.
- No module outside `v2/zhongshu/cognition/nanobot_shim.py` imports `nanobot` internals.
- The single-controller constraint is validated by integration tests.
- All original `main` milestone commands have V2 equivalents.

---

## 14. Migration Phase Summary

| Phase | Key Modules Introduced | Key Sources | Risk |
|-------|----------------------|-------------|------|
| 0 | Documentation | — | Low |
| 1 | Data Schema (奏折) | `models.py` → redesign | Low |
| 2 | Tongzhengsi (Ingress) | `cli.py` → redesign | Low |
| 3 | Archive + Roles | `archive.py`, `roles.py` → migrate | Low |
| 4 | Hanlin / Shiguan (RAG + Memory) | New layer | Medium |
| 5 | Liubu Host Backend + Tools | `backends/host.py` → migrate | Medium |
| 6 | Liubu Container Backend | `refs/pyclaw` → reimplement | High |
| 7 | AI Provider + Zhongshu Cognition | `runtime_bridge.py` → redesign | High |
| 8 | Menxia Sheng (Output Guard) | New layer | Medium |
| 9 | Orchestration + Consolidation | `delegate_command.py` → redesign | High |

---

## 15. Suggested Directory Structure for V2 Implementation

When implementation begins, the V2 code should live in a `v2/` package alongside (not replacing) the existing `secnano/` package until Phase 9 consolidation:

```
secnano/                        ← existing implementation (untouched)
v2/                             ← new V2 implementation
  schemas/                      ← Phase 1: Data Schema (奏折)
    inbound.py
    task.py
    reply.py
    archive.py
    roles.py
    capabilities.py
    cognition.py
  tongzhengsi/                  ← Phase 2: Ingress
    cli_channel.py
    validator.py
    errors.py
  archive/                      ← Phase 3: Archive & State
    tasks.py
    sessions.py
    queries.py
  roles/                        ← Phase 3: Roles & Assets
    loader.py
    registry.py
    memory.py
  hanlin/                       ← Phase 4: RAG + Memory Retrieval
    retriever.py
    indexer.py
    memory_gate.py
  liubu/                        ← Phases 5 & 6: Execution + Tools
    backends/
      base.py
      host.py
      container.py
    container/
      workspace.py
      mounts.py
      secrets.py
      lifecycle.py
      ipc.py
      slots.py                  ← active container slot management + queuing
      writeback.py              ← pre-recycle state writeback to archive
    tools/
      registry.py
      specs.py
    artifacts.py
  providers/                    ← Phase 7: AI Provider
    base.py
    registry.py
    factory.py
  zhongshu/                     ← Phases 7 & 9: Controller + Brain
    cognition/
      runtime.py
      prompting.py
      loop.py
      nanobot_shim.py           ← optional, isolates nanobot dependency
    orchestrator/
      sessions.py
      planner.py
      dispatcher.py
      reviewer.py
  menxia/                       ← Phase 8: Output Guard
    guard.py
    policies/
      base.py
      format.py
      safety.py
  config/                       ← Support: Configuration Management
    schema.py
    loader.py
    paths.py
  skills/                       ← Support: Skill Registry
    loader.py
    registry.py
    parser.py
  adapters/                     ← Support: Capability Adapter
    base.py
    registry.py
    capability_specs.py
docs/                           ← V2 design documents (this branch)
refs/                           ← Reference material (unchanged)
packages/
  nanobot/                      ← Cognition shim only; no other nanobot surface
roles/                          ← Role assets (migrated with POLICY.json added)
runtime/                        ← Runtime data (archive, sessions, artifacts)
```
