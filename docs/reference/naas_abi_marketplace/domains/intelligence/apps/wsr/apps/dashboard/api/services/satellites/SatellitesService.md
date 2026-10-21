# SatellitesService

## What it is
- An asynchronous service that retrieves satellite records via an injected adapter.
- Provides a failure-tolerant `get_satellites()` method that returns an empty list on error and logs a warning.

## Public API
- `class SatellitesService(ISatellitesService)`
  - `__init__(adapter: ISatelliteAdapter) -> None`
    - Stores the adapter used to fetch satellites.
  - `async get_satellites() -> list[SatelliteRecord]`
    - Returns `await self._adapter.fetch()`.
    - On any exception: logs a warning and returns `[]`.

## Configuration/Dependencies
- Depends on:
  - `ISatelliteAdapter` (from `services.satellites.SatellitesPort`)
    - Must provide `async fetch() -> list[SatelliteRecord]` (as called by this service).
  - `ISatellitesService` (from `services.satellites.SatellitesPort`) as the base interface.
  - `SatelliteRecord` (from `ports.models`) as the return item type.
- Logging:
  - Uses `logging.getLogger(__name__)`.
  - Warns on failure: `"[satellites] fetch failed: %s"`.

## Usage
```python
import asyncio
from naas_abi_marketplace.domains.intelligence.apps.wsr.apps.dashboard.api.services.satellites.SatellitesService import (
    SatellitesService,
)

class DummyAdapter:
    async def fetch(self):
        return []  # should be list[SatelliteRecord]

async def main():
    service = SatellitesService(adapter=DummyAdapter())
    satellites = await service.get_satellites()
    print(satellites)

asyncio.run(main())
```

## Caveats
- Exceptions from the adapter are swallowed:
  - Callers receive `[]` whether there are no satellites or the fetch failed; only logs indicate failure.
