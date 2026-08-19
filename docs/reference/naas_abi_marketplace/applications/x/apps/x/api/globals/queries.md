# `globals/queries.py`

## What it is
Publishes `globals/queries.json`, a JSON document containing sanitized query dropdown values derived from a `SnapshotContext`.

## Public API
- `publish(ctx: SnapshotContext) -> dict`
  - Builds a list of query entries from `ctx.queries`.
  - Skips entries with an empty/blank `query`.
  - Generates a slug via `slugify(name or query)`.
  - Persists the result to `globals/queries.json` via `ctx.save_json(...)`.
  - Returns the document dict: `{"updated_at": ..., "queries": ...}`.

## Configuration/Dependencies
- Depends on `naas_abi_marketplace.applications.x.apps.x.api.common`:
  - `SnapshotContext` (must provide `queries`, `built_at`, and `save_json(...)`)
  - `slugify(...)`
- Expects `ctx` to have:
  - `ctx.queries`: iterable of dict-like entries with optional keys: `query`, `name`, `label`
  - `ctx.built_at`: datetime-like object with `.isoformat()`
  - `ctx.save_json(folder: str, filename: str, doc: dict)`

## Usage
```python
from datetime import datetime
from naas_abi_marketplace.applications.x.apps.x.api.globals.queries import publish

class Ctx:
    built_at = datetime.utcnow()
    queries = [
        {"name": "Top users", "query": "SELECT * FROM users", "label": "Users"},
        {"query": "  "},  # skipped
    ]
    def save_json(self, folder, filename, doc):
        print(folder, filename, doc)

doc = publish(Ctx())
print(doc["updated_at"], len(doc["queries"]))
```

## Caveats
- Entries with missing/blank `query` are ignored.
- `label` falls back in order: `label` → `name` → `query` (all coerced to `str`).
