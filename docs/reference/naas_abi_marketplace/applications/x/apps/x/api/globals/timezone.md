# timezone

## What it is
Publishes a `globals/timezone.json` document containing timezone filter values, using a provided snapshot context.

## Public API
- `DEFAULT_TIMEZONES: list[dict]`
  - Default timezone entries (each with `id` and `label`).
- `publish(ctx: SnapshotContext) -> dict`
  - Builds the timezone document, saves it as `globals/timezone.json`, and returns the generated dict.

## Configuration/Dependencies
- Depends on `naas_abi_marketplace.applications.x.apps.x.api.common.SnapshotContext`.
  - Expected to provide:
    - `built_at` (datetime-like with `.isoformat()`).
    - `save_json(folder: str, filename: str, doc: dict)`.

## Usage
```python
from datetime import datetime
from naas_abi_marketplace.applications.x.apps.x.api.globals import timezone

class DummyCtx:
    built_at = datetime.utcnow()
    def save_json(self, folder, filename, doc):
        print(folder, filename, doc["default"])

doc = timezone.publish(DummyCtx())
print(doc["updated_at"])
```

## Caveats
- `publish()` always sets `"default"` to `"UTC"` and uses the hard-coded `DEFAULT_TIMEZONES`.
