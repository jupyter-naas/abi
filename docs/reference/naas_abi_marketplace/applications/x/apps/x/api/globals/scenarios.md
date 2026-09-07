# `globals.scenarios` (`publish`)

## What it is
Publishes `globals/scenarios.json`, containing scenario filter values plus an `updated_at` timestamp.

## Public API
- `publish(ctx: SnapshotContext) -> dict`
  - Builds a document with:
    - `updated_at`: `ctx.built_at` as ISO-8601 string
    - `scenarios`: `ctx.scenarios`
  - Persists it via `ctx.save_json("globals", "scenarios.json", doc)`
  - Returns the generated document.

## Configuration/Dependencies
- Depends on `SnapshotContext` from `naas_abi_marketplace.applications.x.apps.x.api.common`.
- `SnapshotContext` must provide:
  - `built_at` (datetime-like with `.isoformat()`)
  - `scenarios` (JSON-serializable value, expected to include fields like `id`, `label`, `start_time`, `end_time`)
  - `save_json(folder: str, filename: str, doc: dict)`

## Usage
```python
from datetime import datetime
from naas_abi_marketplace.applications.x.apps.x.api.globals.scenarios import publish

class DummyCtx:
    built_at = datetime.utcnow()
    scenarios = [{"id": "s1", "label": "Scenario 1", "start_time": None, "end_time": None}]
    def save_json(self, folder, filename, doc):
        # Replace with real persistence
        print(folder, filename, doc)

doc = publish(DummyCtx())
print(doc["updated_at"])
```

## Caveats
- `ctx.scenarios` must be JSON-serializable for `save_json` to succeed.
- The function does not validate scenario fields; it writes whatever is provided in `ctx.scenarios`.
