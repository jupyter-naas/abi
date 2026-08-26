# ConflictService

## What it is
- A small service implementing `IConflictService` that retrieves `ConflictEvent` items by delegating to an injected `IConflictAdapter`.

## Public API
- `class ConflictService(IConflictService)`
  - `__init__(adapter: IConflictAdapter) -> None`
    - Stores the provided adapter for later use.
  - `get_events() -> list[ConflictEvent]`
    - Returns conflict events from `self._adapter.fetch()`.

## Configuration/Dependencies
- Imports:
  - `ports.models.ConflictEvent` — return type for events.
  - `services.conflict.ConflictPort.IConflictAdapter` — adapter interface (must provide `fetch()`).
  - `services.conflict.ConflictPort.IConflictService` — service interface implemented by this class.
- Dependency injection:
  - Requires an `IConflictAdapter` instance at construction.

## Usage
```python
from naas_abi_marketplace.domains.intelligence.apps.wsr.apps.dashboard.api.services.conflict.ConflictService import (
    ConflictService,
)

# Minimal adapter stub
class DummyAdapter:
    def fetch(self):
        return []  # should be list[ConflictEvent] in real usage

service = ConflictService(adapter=DummyAdapter())
events = service.get_events()
print(events)
```

## Caveats
- `get_events()` is a thin pass-through; any errors and data shaping depend entirely on the adapter’s `fetch()` implementation.
- The adapter is expected to return `list[ConflictEvent]`; mismatched types will propagate to callers.
