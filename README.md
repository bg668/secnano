# secnano architecture-v2

This branch started as a clean V2 workspace for architecture definition, migration governance, and future implementation scaffolding, and now includes the V2 runnable implementation defined by the roadmap.

## Workspace layout

- `docs/architecture/` — canonical V2 architecture overview and module design notes in English and Chinese
- `docs/mapping/` — mapping from legacy `main` structures to V2 targets
- `docs/plan/` — V2 roadmap documents
- `docs/migration/` — branch migration strategy and branch-purpose guidance
- `docs/decisions/` — architecture decision records for V2 governance
- `refs/legacy-index.md` — lightweight reference index pointing back to useful legacy areas on `main`
- `src/v2/` — V2 runnable implementation (schemas, ingress, archive, roles, execution backend, cognition, guard, CLI wiring)
- `secnano_v2/` — command compatibility module for `python -m secnano_v2`
- `tests/v2/` — V2 unit and integration tests
- `scripts/` — reserved for project scripts

## Branch boundary

- `architecture-v2` is documentation-first and V2-only.
- Legacy code from `main` is reference material, not active implementation in this branch.
- Formal V2 implementation should be added only under `src/`, `tests/`, and `scripts/` after the relevant design and decision records are in place.
- Bulk legacy code should stay on `main`; this branch keeps only indexed references, not copied historical implementations.

## Recommended reading order

1. `docs/architecture/zh/README.md` or `docs/architecture/en/README.md`
2. `docs/mapping/main-to-v2-mapping.md`
3. `docs/plan/roadmap.md`
4. `docs/migration/migration-strategy.md`
5. `docs/decisions/ADR-001-branch-boundary.md`
6. `refs/legacy-index.md`
