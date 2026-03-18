# ADR-001: Branch Boundary for `architecture-v2`

- Status: Accepted
- Date: 2026-03-18

## Context

The `architecture-v2` branch was created to define a new architecture without carrying over the mixed assumptions of the legacy implementation on `main`. Before new code is added, the branch needs a clear rule for what belongs in active workspace paths and what remains reference-only.

## Decision

1. `architecture-v2` is a V2-only workspace.
2. `main` remains the source of legacy implementation history and detailed reference material.
3. `refs/` may contain only lightweight reference indexing that points implementers back to useful legacy areas on `main`.
4. `src/`, `tests/`, and `scripts/` are reserved for formal V2 content only.
5. Legacy code must not stay in formal implementation paths, including `src/`, `tests/`, `scripts/`, or any other directory presented as active implementation.

## Consequences

- Carried-over implementation directories from `main` should be removed rather than preserved as misleading active code.
- Future V2 implementation starts from clean placeholders and follows the architecture, mapping, and planning documents in this branch.
- Historical material is still accessible through the `main` branch and the lightweight index in `refs/legacy-index.md`.
