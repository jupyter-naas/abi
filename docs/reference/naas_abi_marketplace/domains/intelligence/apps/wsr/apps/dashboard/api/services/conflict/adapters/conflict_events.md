# ConflictEventsAdapter

## What it is
- A conflict-events adapter that serves a **fully static**, OSINT-sourced dataset of `ConflictEvent` entries.
- Provides **20 named sites** (Iran nuclear/military, Israel sites, US CENTCOM forward bases, and regional flashpoints) for use in a dashboard/API context.

## Public API
- `class ConflictEventsAdapter(IConflictAdapter)`
  - `fetch() -> list[ConflictEvent]`
    - Returns the module’s static list of `ConflictEvent` objects.

## Configuration/Dependencies
- Depends on:
  - `ports.models.ConflictEvent` (data model)
  - `services.conflict.ConflictPort.IConflictAdapter` (adapter interface)
- Data:
  - Module-level `_EVENTS: list[ConflictEvent]` holding the static dataset.

## Usage
```python
from services.conflict.adapters.conflict_events import ConflictEventsAdapter

adapter = ConflictEventsAdapter()
events = adapter.fetch()

print(len(events))          # 20
print(events[0].id)         # e.g., "natanz"
print(events[0].name)       # e.g., "Natanz Enrichment Complex"
```

## Caveats
- `fetch()` returns the `_EVENTS` list directly (not a copy). Mutating the returned list or its items affects subsequent calls.
