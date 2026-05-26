# EventFactory

## What it is
Factory for building a default `EventService` backed by `EventSQLiteAdapter`. The database file is placed under the project's `storage/` folder (created if absent).

## Public API

### `class EventFactory`
- `EventSQLite_find_storage(bus: BusService | None = None, subpath: str = "events.sqlite", needle: str = "storage") -> EventService`
  - Locates (or creates) the `storage/` folder via `naas_abi_core.utils.Storage.find_storage_folder`.
  - Places the SQLite file under `<storage>/events/<subpath>` (subpath is prefixed with `events/` if not already).
  - Returns an `EventService` wired to that adapter and the provided bus.

## Configuration/Dependencies
- `EventSQLiteAdapter` (sibling adapter).
- `BusService` (optional).
- `naas_abi_core.utils.Storage.find_storage_folder`.

## Usage

```python
from naas_abi_core.services.event.EventFactory import EventFactory

events = EventFactory.EventSQLite_find_storage(bus=bus_service)
```

## Caveats
- If no `bus` is passed, `events.subscribe(...)` raises `RuntimeError`. `publish` and `query` still work — the event log remains durable.
