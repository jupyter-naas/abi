# ADR: Code-Data Symmetry — Mirrored Storage Paths

- Status: Accepted
- Date: 2025-08-24

## Context

ABI modules produce and consume data files (CSVs, Parquet, ontologies, cached API responses) stored under `storage/datastore/`. Without a convention, developers chose arbitrary paths, leading to:

- Modules failing silently when their data directory did not exist.
- Inconsistent path structures making it impossible to predict where a module's data lives.
- Manual directory creation steps buried in setup documentation.

## Decision

Establish **Code-Data Symmetry**: a module's data storage path must mirror its code path.

A module at `src/core/modules/linkedin/` stores its data at `storage/datastore/core/modules/linkedin/`. The same pattern applies to all tiers (core, custom, marketplace).

To enforce this, introduce `ensure_data_directory(module_path: str) -> Path` in `abi/utils/Storage.py`. This utility:
- Derives the storage path from the module's code path.
- Creates the directory tree with `exist_ok=True` (idempotent, never fails on re-run).
- Returns the absolute path for use in configuration.

Modules call `ensure_data_directory(__file__)` in their `definitions.py` to self-heal their storage structure on every startup.

## Consequences

### Positive
- Zero manual directory setup: modules create their own data directories on first run.
- Consistent, predictable data layout across all modules and environments.
- `storage/` tree mirrors `src/` tree, making data provenance immediately obvious.

### Tradeoffs
- The symmetry convention is enforced by documentation and the utility function, not by a linter or test.
- Modules that do not call `ensure_data_directory()` are not protected by the convention.
- Renaming a module's code path requires migrating its data directory manually.
