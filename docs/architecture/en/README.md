# V2 Architecture Documentation

This directory holds the English V2 architecture set for the `architecture-v2` branch.

## Documents

- `architecture-overview.md` — canonical V2 architecture goals, module topology, and dependency rules
- `module-design.md` — concise per-module design summary for future implementation work

## Reading order

1. Read `architecture-overview.md` for branch purpose and the full V2 system model.
2. Read `module-design.md` for the stable module breakdown that should guide future code placement under `src/`.
3. Read `../../mapping/main-to-v2-mapping.md` for how legacy `main` areas relate to the V2 design.
4. Read `../../migration/migration-strategy.md` and `../../decisions/ADR-001-branch-boundary.md` before starting any implementation.
