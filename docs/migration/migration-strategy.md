# Migration Strategy for `architecture-v2`

## Purpose of the branch

`architecture-v2` exists to define and prepare the second-generation architecture as a clean workspace. Its immediate purpose is to freeze documentation, structure, governance, and implementation boundaries before formal V2 code is written.

## Relationship with `main`

The `main` branch remains the source of legacy implementation history and operational reference. It is useful for understanding prior behavior, data flows, and reusable ideas, but it is not the formal implementation surface for V2.

## Legacy code policy

Legacy code from `main` is reference material only.

- It may inform new V2 designs.
- It may be consulted when planning interfaces, migrations, and execution semantics.
- It must not remain mixed into active V2 implementation paths.

## Why legacy code should not stay in formal V2 implementation paths

Leaving legacy code under formal implementation directories creates false signals about what is canonical, what is supported, and what should be extended next. It also encourages accidental coupling between the old architecture and the new one, which defeats the purpose of creating a clean V2 boundary.

For that reason, formal V2 paths must start empty or contain only intentional V2 artifacts. Historical material should be referenced, not carried inline.

## Role of `refs/`

The `refs/` directory is for lightweight reference indexing only.

- It may point to useful modules, documents, or subtrees that still live on `main`.
- It must not become a second copy of the legacy codebase.
- It must not be used as a dumping ground for removed implementation directories.

## Implementation entry points

Future formal V2 work should begin only in these top-level placeholders:

- `src/`
- `tests/`
- `scripts/`

Those directories are reserved for V2-only content.
