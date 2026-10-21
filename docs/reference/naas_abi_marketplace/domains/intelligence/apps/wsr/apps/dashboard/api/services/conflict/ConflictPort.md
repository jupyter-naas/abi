# ConflictPort

## What it is
A minimal port module that defines two interface-style classes for working with `ConflictEvent` objects:
- An adapter interface to **fetch** conflict events from a data source.
- A service interface to **expose** conflict events to callers.

## Public API
- `class IConflictAdapter`
  - `fetch() -> list[ConflictEvent]`: Retrieve conflict events (to be implemented by a concrete adapter).
- `class IConflictService`
  - `get_events() -> list[ConflictEvent]`: Provide conflict events to the application layer (to be implemented by a concrete service).

## Configuration/Dependencies
- Imports `ConflictEvent`:
  - `from ports.models import ConflictEvent`

## Usage
```python
from ports.models import ConflictEvent
from naas_abi_marketplace.domains.intelligence.apps.wsr.apps.dashboard.api.services.conflict.ConflictPort import (
    IConflictAdapter,
    IConflictService,
)

class MyConflictAdapter(IConflictAdapter):
    def fetch(self) -> list[ConflictEvent]:
        return []

class MyConflictService(IConflictService):
    def __init__(self, adapter: IConflictAdapter):
        self.adapter = adapter

    def get_events(self) -> list[ConflictEvent]:
        return self.adapter.fetch()

service = MyConflictService(MyConflictAdapter())
events = service.get_events()
```

## Caveats
- These base methods raise `NotImplementedError`; they are intended to be overridden.
- Implementations are expected (by annotation) to return `list[ConflictEvent]`.
