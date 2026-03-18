# Migration Plan V2

## 1. Purpose of This Document

This document defines the phased plan for moving from the current design-only `architecture-v2` branch to a working V2 implementation.

Read alongside:

- `docs/architecture/en/architecture-overview.md` — canonical V2 architecture reference
- `docs/mapping/main-to-v2-mapping.md` — current-to-V2 module mapping and action classifications

---

## 2. Governing Principles

### 2.1 Agent Rules

These rules apply to every phase without exception:

- **Build minimum closed loop around the main chain** — do not build isolated modules that cannot be exercised end-to-end.
- **Framework first, business as samples** — structure and contracts come before real logic; real logic is introduced incrementally.
- **Stubs and mocks must respect formal interfaces** — placeholder implementations must conform to the same types and signatures as their real counterparts.
- **Every delivery must be runnable, observable, and verifiable** — each phase ships a verification command that exercises the current main chain.
- **Roles carry minimum responsibility; RAG is mock-only** — the Hanlin/Shiguan layer is kept as an interface-compliant stub throughout; a real retrieval engine is an optional future extension.
- **`refs/` is reference only** — do not wholesale-copy from `refs/pyclaw` or `refs/nanoclaw`; study and reimplement.

### 2.2 Main Chain

Every phase keeps the following chain runnable end-to-end. From Phase 1 onward, each node exists as either a stub or a real implementation — never absent:

```
CLI → InboundEvent → Orchestrator → Cognition → ExecutionRequest
    → Host Backend → ExecutionResult → Archive → Reply → Guard → CLI Output

Phase 1: all nodes are interface-compliant stubs
Phase 2: CLI and Archive are replaced with real implementations
Phase 3: Host Backend is replaced with a real implementation
Phase 4: Orchestrator and Cognition are replaced with real implementations
Phase 5: Guard is replaced with a real implementation
```

Modules not yet fully implemented are replaced with interface-compliant stubs that satisfy the same type contracts as the real implementation.

### 2.3 Non-Goals

- Do not bulk-port the existing `secnano/` implementation. Carry over design compromises and you erase the reason for V2.
- Do not lock into a single agent framework before the cognition interface is stable.
- Do not modify `main` as part of V2 work.
- Do not import from `refs/pyclaw` or `refs/nanoclaw` as production code.

---

## 3. Phases Overview

| Phase | Name | Goal | Prerequisites |
|-------|------|------|--------------|
| 0 | Architecture Freeze | Design documents complete and agreed | — |
| 1 | Schemas + Main Chain Skeleton | Minimal contracts defined; full chain runnable with stubs | Phase 0 |
| 2 | Ingress + Archive | Real CLI parsing and real task persistence | Phase 1 |
| 3 | Execution (Liubu Host) | Real host backend + tool registry | Phase 2 |
| 4 | Cognition (Zhongshu Sheng) | Real LLM orchestration + AI provider abstraction | Phase 3 |
| 5 | Output Guard + Integration | Real Menxia Sheng gate; full pipeline verified | Phase 4 |

Container backend (full LLM-driven container lifecycle) is a **post-Phase-5 extension**, deferred until the main chain is stable and the need is confirmed.

---

## 4. Phase 0: Architecture Freeze

**Status**: Complete.

**Goal**: Complete and agree on V2 architecture design documents.

**Deliverables**:

- [x] `docs/architecture/en/architecture-overview.md` — V2 module definitions, design principles, court metaphor
- [x] `docs/mapping/main-to-v2-mapping.md` — current-to-V2 mapping with action classifications
- [x] `docs/plan/roadmap.md` — this document

**Done criteria**:

- All three documents are on the `architecture-v2` branch and reviewed.
- Module boundaries, data contracts, and dependency rules are agreed.
- No implementation code has been changed.

---

## 5. Phase 1: Schemas + Main Chain Skeleton

**Goal**: Define the minimal contract types needed by the main chain, then wire up every module as an interface-compliant stub so the chain runs end-to-end from the first commit.

**Deliverables**:

Schemas (contracts only — no business logic):

- `src/v2/schemas/inbound.py` — `InboundEvent`
- `src/v2/schemas/task.py` — `Task`, `ExecutionRequest`, `ExecutionResult`
- `src/v2/schemas/reply.py` — `Reply`
- `src/v2/schemas/archive.py` — `TaskArchiveRecord`
- `src/v2/schemas/roles.py` — `RoleSpec`
- `src/v2/schemas/cognition.py` — `CognitionRequest`, `CognitionResult`

Stubs (interface-compliant, not placeholder strings):

- `src/v2/tongzhengsi/cli_channel.py` — stub: reads `--role` and `--task` from argv, returns hardcoded `InboundEvent`
- `src/v2/zhongshu/orchestrator.py` — stub: receives `InboundEvent`, returns hardcoded `ExecutionRequest` and `Reply`
- `src/v2/zhongshu/cognition/stub.py` — stub: `CognitionRequest` → fixed `CognitionResult`
- `src/v2/liubu/backends/host.py` — stub: `ExecutionRequest` → fixed `ExecutionResult`
- `src/v2/hanlin/retriever.py` — mock (permanent throughout core phases 1–5): `query(str) → []`; real retrieval is an optional Phase 6+ extension per agent rules
- `src/v2/archive/writer.py` — stub: writes `TaskArchiveRecord` as JSON to `runtime/tasks/`
- `src/v2/menxia/guard.py` — stub: passes any `Reply` through unchanged
- `src/v2/__main__.py` — entry point wiring all stubs into the main chain

Tests:

- Unit tests: schema construction, field types, frozen immutability.
- Smoke test: full chain stub run produces a `Reply` and an archive file.

**Design rules**:

- Every stub must import and instantiate the schema types it produces — no bare dicts or untyped strings.
- The Hanlin mock returns an empty list and is never replaced in core phases (RAG is mock-only).
- The orchestrator stub must call the cognition stub and the host backend stub in order, so the chain is structurally correct from day one.

**Done criteria**:

- `python -m secnano_v2 delegate --role demo --task "hello"` prints a reply to stdout and writes a JSON archive file.
- Unit tests pass.

**Verification command**:

```bash
python -m secnano_v2 delegate --role demo --task "hello"
# Expected: prints Reply content; creates runtime/tasks/<task_id>.json
```

---

## 6. Phase 2: Ingress + Archive

**Goal**: Replace the Tongzhengsi stub with real CLI parsing and the archive stub with real file persistence.

**Deliverables**:

- `src/v2/tongzhengsi/cli_channel.py` — real CLI argument parser producing validated `InboundEvent`
- `src/v2/tongzhengsi/validator.py` — input validation and normalisation
- `src/v2/tongzhengsi/errors.py` — structured ingress error types
- `src/v2/archive/writer.py` — real `TaskArchiveRecord` persistence (JSON files under `runtime/tasks/`)
- `src/v2/archive/reader.py` — read interface for archive queries
- `src/v2/roles/loader.py` — role asset loading (`SOUL`, `ROLE`, `MEMORY`, `POLICY` files → `RoleSpec`)

Tests:

- Valid CLI input → `InboundEvent`; malformed input → structured error, not stack trace.
- Archive round-trip: write then read back the same `TaskArchiveRecord`.
- Role loader: missing required file raises structured error.

**Source mapping**: redesign from `secnano/cli.py`, `archive.py`, `roles.py`.

**Done criteria**:

- `python -m secnano_v2 delegate --role <role> --task "<task>"` produces a valid `InboundEvent` and persists a `TaskArchiveRecord`.
- `python -m secnano_v2 delegate --role missing` exits with a structured error message, not a traceback.

**Verification commands**:

```bash
python -m secnano_v2 delegate --role demo --task "write a hello world"
cat runtime/tasks/*.json          # archive file present and valid JSON

python -m secnano_v2 delegate     # missing required arg
# Expected: structured error, exit code != 0
```

---

## 7. Phase 3: Execution (Liubu Host Backend)

**Goal**: Replace the host backend stub with a real execution backend that can run a task and return a structured `ExecutionResult`.

**Deliverables**:

- `src/v2/liubu/backends/base.py` — `ExecutionBackend` protocol
- `src/v2/liubu/backends/host.py` — real host execution backend
- `src/v2/liubu/tools/registry.py` — tool definitions and dispatch
- `src/v2/liubu/tools/specs.py` — tool schema types
- `src/v2/archive/writer.py` — extended to persist `ExecutionResult` alongside `TaskArchiveRecord`

Tests:

- Host backend receives `ExecutionRequest`, runs a trivial tool, returns `ExecutionResult`.
- Tool registry lists and dispatches the built-in tools.
- `ExecutionResult` is persisted to archive.

**Source mapping**: migrate from `backends/host.py`; study `refs/` for tool patterns.

**Done criteria**:

- A sample execution request runs a built-in tool (e.g., `echo`) and the output appears in the archive.
- Orchestrator stub still calls host backend through `ExecutionBackend` protocol; chain remains runnable.

**Verification commands**:

```bash
python -m secnano_v2 delegate --role demo --task "run echo hello"
cat runtime/tasks/*.json          # ExecutionResult present inside archive record
```

---

## 8. Phase 4: Cognition (Zhongshu Sheng)

**Goal**: Replace the cognition stub with a real LLM-driven orchestration layer behind the `CognitionRequest` / `CognitionResult` contract.

**Deliverables**:

- `src/v2/providers/base.py` — `AIProvider` protocol
- `src/v2/providers/openai.py` — OpenAI provider (primary example)
- `src/v2/zhongshu/cognition/runtime.py` — cognition entry point (`CognitionRequest` → `CognitionResult`)
- `src/v2/zhongshu/cognition/prompting.py` — prompt assembly from `RoleSpec` + Hanlin mock context
- `src/v2/zhongshu/orchestrator.py` — real orchestrator: `InboundEvent` → cognition → `ExecutionRequest` → backend → `Reply`
- `src/v2/zhongshu/cognition/nanobot_shim.py` — **optional** shim if `nanobot` is still in use; isolated here only

Tests:

- Prompt assembly from `RoleSpec` plus empty Hanlin context produces a non-empty prompt string.
- Provider protocol: a mock provider returns a `CognitionResult`; swap to real provider by config only.
- Integration: `InboundEvent` → orchestrator → cognition → `ExecutionRequest` → host backend → `Reply`.

**Design rules**:

- `nanobot` (if used) is called only from `nanobot_shim.py`. No other file imports it.
- The Hanlin mock continues returning an empty list; prompting assembles context from role assets only.

**Done criteria**:

- `python -m secnano_v2 delegate --role demo --task "summarise this"` calls the real LLM and returns a coherent reply.
- Swapping provider (OpenAI → Anthropic) requires only a config key change.

**Verification commands**:

```bash
export SECNANO_PROVIDER=openai
python -m secnano_v2 delegate --role demo --task "say hello in three languages"
# Expected: real LLM reply printed; archive contains CognitionResult
```

---

## 9. Phase 5: Output Guard + Integration

**Goal**: Replace the Menxia Sheng stub with a real policy-based validation gate and verify the full main chain end-to-end with all real modules.

**Deliverables**:

- `src/v2/menxia/guard.py` — real output guard (`Reply` → `ApprovedReply | Rejection`)
- `src/v2/menxia/policies/base.py` — policy rule protocol
- `src/v2/menxia/policies/format.py` — format validation (non-empty, valid UTF-8, length limit)
- `src/v2/menxia/policies/safety.py` — content safety rules (initially permissive; tighten per role)
- End-to-end integration test: CLI → `InboundEvent` → orchestrator → cognition → execution → guard → reply.

Tests:

- Approved reply passes through unchanged.
- Reply violating format policy produces a structured `Rejection`, not a raw model string.
- `Rejection` is fed back to the orchestrator (not printed directly to the user).

**Design rules**:

- The guard does not generate content — it only inspects and approves or rejects.
- Policy rules are declarative and do not call the LLM.

**Done criteria**:

- Every reply path passes through the guard before reaching CLI output.
- An intentionally malformed reply (e.g., injected via test) is caught and produces a `Rejection`.
- Full end-to-end integration test passes.

**Verification commands**:

```bash
python -m secnano_v2 delegate --role demo --task "hello"
# Expected: approved reply printed; archive has ApprovedReply record

python -m secnano_v2 self-test --chain
# Expected: runs full chain smoke test; all steps pass
```

---

## 10. Migration Phase Summary

| Phase | Key Modules | Source | Main Chain Status |
|-------|-------------|--------|------------------|
| 0 | Documentation | — | n/a |
| 1 | Schemas + all stubs | New | **Runnable (all stubs)** |
| 2 | Tongzhengsi + Archive | `cli.py`, `archive.py` → redesign | Runnable (real ingress + archive) |
| 3 | Liubu Host Backend | `backends/host.py` → migrate | Runnable (real execution) |
| 4 | Zhongshu Cognition + Provider | `runtime_bridge.py` → redesign | Runnable (real LLM) |
| 5 | Menxia Guard + integration | New | **Fully real** |

---

## 11. Suggested Directory Structure for V2 Implementation

```
src/
  v2/
    schemas/                    ← Phase 1: Data contracts (immutable)
      inbound.py
      task.py
      reply.py
      archive.py
      roles.py
      cognition.py
    tongzhengsi/                ← Phase 2: Ingress (CLI → InboundEvent)
      cli_channel.py
      validator.py
      errors.py
    archive/                    ← Phase 2: Persistence
      writer.py
      reader.py
    roles/                      ← Phase 2: Role asset loading
      loader.py
    liubu/                      ← Phase 3: Execution
      backends/
        base.py
        host.py
      tools/
        registry.py
        specs.py
    providers/                  ← Phase 4: AI provider abstraction
      base.py
      openai.py
    zhongshu/                   ← Phase 4: Orchestrator + Cognition
      orchestrator.py
      cognition/
        runtime.py
        prompting.py
        nanobot_shim.py         ← optional; isolates nanobot dependency
    hanlin/                     ← Mock only (all phases)
      retriever.py              ← returns [] permanently in core phases
    menxia/                     ← Phase 5: Output guard
      guard.py
      policies/
        base.py
        format.py
        safety.py
    __main__.py                 ← Phase 1: entry point wiring the main chain
tests/
scripts/
docs/
refs/                           ← reference index only
```

> **Container backend** (`liubu/backends/container.py` and `liubu/container/`): deferred to Phase 6+. Add only when the host-backend main chain is fully stable and container execution is confirmed necessary.
