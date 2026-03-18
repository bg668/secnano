# V2 Module Design

This document provides a stable module-oriented summary of the V2 architecture defined in `architecture-overview.md`.

## Core formal modules

### Tongzhengsi
- Owns ingress parsing, validation, and normalisation.
- Produces `InboundEvent` objects only.
- Must not perform orchestration, archive access, or model execution.

### Zhongshu Sheng
- Owns controller policy, session-level routing, and top-level reasoning flow.
- Decides whether to reply directly, request follow-up input, or delegate execution.
- Interacts with the cognition layer and execution layer through stable contracts.

### Hanlin / Shiguan
- Owns retrieval, memory curation, and historical context supply.
- Reads from archives and role memories to prepare context for reasoning.
- Must gate any long-term memory promotion through explicit rules.

### Liubu
- Owns execution backends, tool registry, container lifecycle, and artifact handling.
- Host and container execution both live here.
- Reference implementations from `main` may inform design but must not remain as formal V2 code.

### Menxia Sheng
- Owns reply validation and output gating.
- Approves, filters, or rejects outbound replies.
- Must not generate content itself.

## Supporting formal modules

### Data Schema
- Shared immutable contracts used by all formal V2 modules.
- Defines canonical types such as `InboundEvent`, `ExecutionRequest`, `ExecutionResult`, and `Reply`.

### Roles & Assets
- Loads and validates role assets such as SOUL, ROLE, MEMORY, and POLICY files.
- Supplies stable role definitions to the controller and execution layers.

### Archive & State
- Persists task records, session state, and execution outputs.
- Provides structured query access for retrieval and audit use cases.

### Capability Adapter / Provider / Config / Skills
- Isolate external integrations behind explicit internal contracts.
- Allow V2 to change providers or capabilities without leaking external framework assumptions across the workspace.

## Directory rule for future implementation

When implementation begins on this branch:

- `src/` contains V2 formal source code only.
- `tests/` contains V2 formal tests only.
- `scripts/` contains V2 formal project scripts only.
- Legacy code from `main` must stay out of those directories.
