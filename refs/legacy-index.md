# Legacy Reference Index

This directory intentionally contains an index only. Legacy implementation should remain on `main`, not be copied into the formal V2 workspace.

## Reference areas on `main`

### Core legacy implementation
- `main:secnano/` — original Python package and CLI implementation
- `main:roles/` — legacy role asset examples and governance files
- `main:packages/nanobot/` — compatibility-stage upstream shim area

### Legacy documentation worth reviewing
- `main:docs/module_boundary_checklist.md` — original architecture and boundary discussion
- `main:docs/development_milestones.md` — milestone-based implementation history
- `main:docs/project_progress.md` — prior completion tracking and delivery status

### External-style reference material previously carried on this branch
- `main:refs/pyclaw/` — Python container runtime reference concepts
- `main:refs/nanoclaw/` — TypeScript orchestration and skills reference concepts

## Usage rule

Use this index to locate historical material when planning V2 work. Do not copy legacy trees wholesale into `architecture-v2`; port only intentionally redesigned V2 content into formal implementation paths.
