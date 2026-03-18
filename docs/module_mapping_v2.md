# Module Mapping V2

## 1. Purpose of This Document

This document maps every current file area and module in the `main` implementation to a specific V2 architecture destination (defined in `architecture_v2.md`).

For each area the mapping indicates:

- **Current location**: where the code lives today.
- **V2 destination**: which V2 module it belongs to.
- **Action**: what to do with it during V2 implementation.

Action categories:

| Action | Meaning |
|--------|---------|
| `KEEP AS REF` | Preserve as reference only; do not copy to V2 code yet. Study the design and protocols. |
| `MIGRATE LATER` | Reusable; copy and adapt into V2 in the relevant phase. |
| `REDESIGN` | The concept is needed but the current implementation should be rewritten from scratch for V2. |
| `SPLIT` | One current file/area maps to multiple V2 modules; must be separated. |
| `MERGE` | Multiple current files/areas map to one V2 module; should be consolidated. |
| `DEPRECATE` | Not needed in V2; do not carry forward. |

---

## 2. Documentation (`docs/`)

| Current File | Content | V2 Destination | Action |
|-------------|---------|----------------|--------|
| `docs/README.md` | Navigation guide | Replace with V2 navigation guide | `REDESIGN` |
| `docs/module_boundary_checklist.md` | Original 12-module architecture spec | `architecture_v2.md` supersedes this for V2; keep in `main` as historical ref | `KEEP AS REF` |
| `docs/development_milestones.md` | M0–M4 milestones | `migration_plan_v2.md` defines V2 phases; old milestones apply to `main` only | `KEEP AS REF` |
| `docs/project_progress.md` | Current completion status | V2 has its own progress tracking; keep `main` tracker in `main` | `KEEP AS REF` |
| `docs/architecture_v2.md` | **V2 architecture reference** | This is the V2 canonical architecture doc | **NEW (this branch)** |
| `docs/module_mapping_v2.md` | **V2 module mapping** | This document | **NEW (this branch)** |
| `docs/migration_plan_v2.md` | **V2 migration plan** | V2 phased implementation roadmap | **NEW (this branch)** |

---

## 3. Reference Material (`refs/`)

### 3.1 `refs/pyclaw/` — Python Container Runtime Reference

| Area | Content | V2 Destination | Action |
|------|---------|----------------|--------|
| `refs/pyclaw/router.py` | IPC message routing | Liubu container backend | `KEEP AS REF` |
| `refs/pyclaw/group_queue.py` | Group-based task queue | Liubu container backend | `KEEP AS REF` |
| `refs/pyclaw/container_runner.py` | Container lifecycle management | Liubu container backend | `KEEP AS REF` |
| `refs/pyclaw/task_scheduler.py` | Task scheduling logic | Liubu container backend | `KEEP AS REF` |
| `refs/pyclaw/db.py` | Persistence layer | Liubu artifact manager / archive | `KEEP AS REF` |
| `refs/pyclaw/bus/` | Event bus and queue | Liubu IPC protocol reference | `KEEP AS REF` |
| `refs/pyclaw/channels/` | Channel abstractions | Liubu IPC / Tongzhengsi channel adapters | `KEEP AS REF` |
| `refs/pyclaw/sender_allowlist.py` | Allowlist security | Menxia Sheng policy / Liubu security | `KEEP AS REF` |
| `refs/pyclaw/mount_security.py` | Mount access control | Liubu artifact manager security | `KEEP AS REF` |

### 3.2 `refs/nanoclaw/` — TypeScript Container Orchestration Reference

| Area | Content | V2 Destination | Action |
|------|---------|----------------|--------|
| `refs/nanoclaw/src/` | Core TypeScript modules (container-runner, group-queue, task-scheduler, IPC) | Liubu architecture reference | `KEEP AS REF` |
| `refs/nanoclaw/docs/` | Architecture docs (nanorepo-architecture, skills-as-branches, nanoclaw-architecture-final) | Inform Liubu + Hanlin/Shiguan design | `KEEP AS REF` |
| `refs/nanoclaw/setup/` | Service initialization scripts | Liubu bootstrap reference | `KEEP AS REF` |
| `refs/nanoclaw/.claude/skills/` | Skill implementations (Slack, Discord, Gmail, Telegram, etc.) | Skill registry format reference | `KEEP AS REF` |

**Note**: No code is imported from `refs/nanoclaw/`. TypeScript code is architecture reference only.

---

## 4. Runtime Bridge (`secnano/runtime_bridge.py`)

| Current Area | Content | V2 Destination | Action |
|-------------|---------|----------------|--------|
| `runtime_bridge.py` | Shim wrapping `nanobot.agent.loop.AgentLoop` | Zhongshu Sheng — cognition sub-layer shim | `REDESIGN` |

**Notes**:

- The current `runtime_bridge.py` directly imports `nanobot` internals and inherits `nanobot`'s config path assumptions.
- In V2, the cognition sub-layer shim must be redesigned to wrap `nanobot.agent.loop` through a stable internal interface (`CognitionRequest` → `CognitionResult`) without leaking `nanobot` internals to any other layer.
- Until the cognition sub-layer is fully redesigned, a minimal shim may remain behind this interface for `nanobot` compatibility.
- The `~/.nanobot` path assumption and `nanobot.config.*` dependencies must be **removed** in V2.

---

## 5. Data Models (`secnano/models.py`)

| Current Area | Content | V2 Destination | Action |
|-------------|---------|----------------|--------|
| `models.py` — `DelegateRequest` | Task delegation input | Data Schema — `Task` / `ExecutionRequest` | `REDESIGN` |
| `models.py` — `DelegateResult` | Delegation output | Data Schema — `ExecutionResult` / `Reply` | `REDESIGN` |
| `models.py` — `TaskArchiveRecord` | Archived task record | Data Schema — `TaskArchiveRecord` | `MIGRATE LATER` |

**Notes**:

- The current models are functional but not fully typed as immutable value objects.
- In V2, the Data Schema (奏折) layer requires strict schema definitions with no embedded logic.
- `TaskArchiveRecord` is the most stable and can be migrated with minimal changes.
- `DelegateRequest` and `DelegateResult` should be redesigned into the richer V2 contract types (`InboundEvent`, `Task`, `ExecutionRequest`, `ExecutionResult`, `Reply`).

---

## 6. Delegate Flow (`secnano/delegate_command.py` and related)

| Current Area | Content | V2 Destination | Action |
|-------------|---------|----------------|--------|
| `delegate_command.py` — role selection | Selects role for task | Zhongshu Sheng — orchestration sub-layer | `MIGRATE LATER` |
| `delegate_command.py` — backend selection | Selects host vs pyclaw_container | Zhongshu Sheng → Liubu dispatch | `MIGRATE LATER` |
| `delegate_command.py` — result validation | Validates execution result | Zhongshu Sheng — orchestration sub-layer | `MIGRATE LATER` |
| `delegate_command.py` — archive write | Writes TaskArchiveRecord | Archive / State module | `MIGRATE LATER` |

**Notes**:

- The current delegate command mixes orchestration decisions, execution dispatch, and archiving in one file. This is appropriate for the current `main` milestone-based implementation.
- In V2, these concerns must be separated across Zhongshu Sheng orchestration, Liubu execution, and the Archive module.
- The role-selection and task-routing logic is reusable and should be migrated in Phase 3.

---

## 7. Roles and Memory (`secnano/roles.py`, `secnano/roles_command.py`)

| Current Area | Content | V2 Destination | Action |
|-------------|---------|----------------|--------|
| `roles.py` — role loading | Reads SOUL/ROLE/MEMORY from filesystem | Roles & Assets module | `MIGRATE LATER` |
| `roles.py` — role listing | Lists available roles | Roles & Assets module | `MIGRATE LATER` |
| `roles.py` — memory promotion | Promotes task insight to role memory | Hanlin / Shiguan — memory promotion | `SPLIT` |
| `roles_command.py` — CLI commands | `roles list`, `roles show`, `roles promote-memory` | Tongzhengsi (CLI ingress) → command handlers | `REDESIGN` |

**Notes**:

- Role loading logic is stable and reusable; migrate into the Roles & Assets module in Phase 2.
- Memory promotion currently lives in `roles.py` but in V2 it belongs to the Hanlin/Shiguan layer with explicit filtering rules; extract separately.
- CLI command handlers should be refactored so that Tongzhengsi dispatches `InboundEvent` objects and the business logic lives in the relevant V2 modules.

---

## 8. Audit and Archive (`secnano/archive.py`, `secnano/audit_command.py`)

| Current Area | Content | V2 Destination | Action |
|-------------|---------|----------------|--------|
| `archive.py` — TaskArchiveRecord persistence | JSON-based task record storage | Archive & State module | `MIGRATE LATER` |
| `archive.py` — task listing and retrieval | Read archive records | Archive & State module | `MIGRATE LATER` |
| `audit_command.py` — `audit list` / `audit show` | CLI read access to archive | Tongzhengsi dispatch → Archive module query | `MIGRATE LATER` |

**Notes**:

- The archive implementation is well-scoped and aligns with V2 requirements.
- The main V2 change is: archive retrieval results should feed into the Hanlin/Shiguan retrieval layer for RAG, not be accessed directly by all modules.
- Migrate largely as-is in Phase 2; add the retrieval interface hook in Phase 4.

---

## 9. Runtime Checks (`secnano/runtime_command.py`)

| Current Area | Content | V2 Destination | Action |
|-------------|---------|----------------|--------|
| `runtime_command.py` — `runtime inspect` | Lists registered adapters and backends | Configuration Management / Capability Adapter | `MIGRATE LATER` |
| `runtime_command.py` — `runtime validate` | Validates runtime prerequisites | Configuration Management / doctor | `MIGRATE LATER` |

---

## 10. Adapters and Tools (`secnano/adapters/`, `secnano/tools_command.py`)

| Current Area | Content | V2 Destination | Action |
|-------------|---------|----------------|--------|
| `adapters/base.py` — `CapabilityAdapter` protocol | Adapter interface contract | Capability Adapter module | `MIGRATE LATER` |
| `adapters/registry.py` — adapter registry | Registered adapters list | Capability Adapter module | `MIGRATE LATER` |
| `tools_command.py` — tool catalog output | Lists available tools | Liubu — Tool Registry | `MIGRATE LATER` |

**Notes**:

- The `CapabilityAdapter` protocol defined in `adapters/base.py` is a good starting point for V2 but should be expanded to include a `CapabilityDescriptor` type that aligns with V2 data schema conventions.
- The tool registry needs to be promoted from a simple catalog to a first-class registry with permission enforcement (enforced at Liubu execution time).

---

## 11. Execution Backends (`secnano/backends/`)

| Current Area | Content | V2 Destination | Action |
|-------------|---------|----------------|--------|
| `backends/base.py` — `ExecutionBackend` protocol | Backend interface contract | Liubu backend protocol | `MIGRATE LATER` |
| `backends/host.py` — host execution | In-process execution backend | Liubu — Host Backend | `MIGRATE LATER` |
| `backends/pyclaw_container.py` — container validation | pyclaw container backend (validation only) | Liubu — Container Backend | `REDESIGN` |

**Notes**:

- `backends/host.py` is functional and reusable; migrate to Liubu Host Backend in Phase 5.
- `backends/pyclaw_container.py` currently only validates prerequisites; it does not execute real container workloads. In V2, the container backend should be redesigned following `refs/pyclaw` protocols to implement full container lifecycle management.

---

## 12. CLI Entry Point (`secnano/cli.py`)

| Current Area | Content | V2 Destination | Action |
|-------------|---------|----------------|--------|
| `cli.py` — argument parsing and dispatch | Main CLI dispatcher | Tongzhengsi — CLI ingress channel | `REDESIGN` |

**Notes**:

- In V2, the CLI is one input channel handled by Tongzhengsi. The CLI parser should produce `InboundEvent` objects and pass them to the Zhongshu Sheng orchestrator.
- The current monolithic `cli.py` dispatch pattern can be redesigned as a thin ingress channel adapter.

---

## 13. `packages/nanobot/`

| Current Area | Content | V2 Destination | Action |
|-------------|---------|----------------|--------|
| `packages/nanobot/` | Currently empty; placeholder for compatibility shim | Zhongshu Sheng — cognition sub-layer shim only | `REDESIGN` |

**Notes**:

- In V2, `packages/nanobot/` should contain **only** the minimal shim that wraps `nanobot.agent.loop.AgentLoop` behind the internal `CognitionRequest` / `CognitionResult` interface.
- It must not expose any `nanobot` internals to other modules.
- It must not own config loading, CLI assembly, or any path conventions.

---

## 14. Roles Directory (`roles/`)

| Current Area | Content | V2 Destination | Action |
|-------------|---------|----------------|--------|
| `roles/general_office/` | Default role assets (SOUL, ROLE, MEMORY, skills) | Roles & Assets module | `MIGRATE LATER` |

**Notes**:

- Role asset format is stable. Migrate as-is.
- V2 adds explicit `POLICY.json` per role. Add this file to existing roles during Phase 2.

---

## 15. Runtime Directory (`runtime/`)

| Current Area | Content | V2 Destination | Action |
|-------------|---------|----------------|--------|
| `runtime/tasks/` | Task archive JSON records | Archive & State module | `MIGRATE LATER` |
| `runtime/sessions/` | Session state (optional) | Archive & State module | `MIGRATE LATER` |

---

## 16. Summary by V2 Module

| V2 Module | Sources (Current Files) | Primary Action |
|-----------|------------------------|----------------|
| Data Schema (奏折) | `models.py`, `delegate_command.py` types | `REDESIGN` (expand and strictly type) |
| Tongzhengsi (Ingress) | `cli.py`, channel adapters | `REDESIGN` (ingress → InboundEvent) |
| Zhongshu Sheng — Orchestration | `delegate_command.py` core logic | `MIGRATE LATER` + `SPLIT` |
| Zhongshu Sheng — Cognition | `runtime_bridge.py` | `REDESIGN` (stable interface) |
| Hanlin / Shiguan (RAG + Memory) | `roles.py` promote-memory, `archive.py` retrieval | `SPLIT` + new retrieval layer |
| Liubu — Host Backend | `backends/host.py` | `MIGRATE LATER` |
| Liubu — Container Backend | `backends/pyclaw_container.py`, `refs/pyclaw` | `REDESIGN` (full lifecycle) |
| Liubu — Tool Registry | `tools_command.py`, `adapters/registry.py` | `MIGRATE LATER` + expand |
| Menxia Sheng (Output Guard) | *(Not yet implemented)* | **NEW** |
| Roles & Assets | `roles/`, `roles.py` loader | `MIGRATE LATER` |
| Archive & State | `archive.py`, `runtime/tasks/` | `MIGRATE LATER` |
| Capability Adapter | `adapters/base.py`, `adapters/registry.py` | `MIGRATE LATER` + `REDESIGN` descriptor |
| Configuration Management | *(Minimal currently)* | `REDESIGN` (decouple from nanobot) |
| AI Provider | *(Not yet implemented)* | **NEW** |
| Skill Registry | *(Not yet implemented)* | **NEW** |
| `packages/nanobot/` shim | `runtime_bridge.py` essence | `REDESIGN` (isolate behind interface) |
| `refs/pyclaw` | Reference only | `KEEP AS REF` |
| `refs/nanoclaw` | Reference only | `KEEP AS REF` |

---

## 17. What Future Implementers Should Do First

When beginning V2 implementation (see also `migration_plan_v2.md`):

1. **Start with Data Schema definitions** — Define all V2 contract types as immutable dataclasses or Pydantic models. Every other module depends on these.
2. **Implement Tongzhengsi skeleton** — Create a minimal CLI ingress adapter that parses input and emits `InboundEvent`. This unblocks end-to-end testing.
3. **Stub the Menxia Sheng interface** — Even if the guard logic is trivial at first, establishing the boundary early prevents output from bypassing the guard in later implementations.
4. **Migrate archive and roles assets** — These are the most stable current implementations. Migrate them early to enable integration testing.
5. **Redesign the cognition shim** — Wrap `nanobot` (or any replacement) behind `CognitionRequest` / `CognitionResult`. Isolate this before adding more orchestration logic.
6. **Do not copy `refs/pyclaw` or `refs/nanoclaw` code directly** — Study the protocols; implement them natively in the Liubu container backend.
