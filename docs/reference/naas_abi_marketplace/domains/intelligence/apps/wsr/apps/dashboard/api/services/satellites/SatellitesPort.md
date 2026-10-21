# SatellitesPort

## What it is
Defines two asynchronous interface (port) classes for working with satellite data:
- An adapter interface to fetch satellite records from a source.
- A service interface to expose satellite records to the application.

## Public API
- `class ISatelliteAdapter`
  - `async fetch() -> list[SatelliteRecord]`
    - Contract for retrieving satellite records from an external/source system.

- `class ISatellitesService`
  - `async get_satellites() -> list[SatelliteRecord]`
    - Contract for application-level access to satellite records.

## Configuration/Dependencies
- Depends on `SatelliteRecord` imported from `ports.models`.

## Usage
Implement these interfaces in your own adapter/service classes:

```python
from ports.models import SatelliteRecord
from naas_abi_marketplace.domains.intelligence.apps.wsr.apps.dashboard.api.services.satellites.SatellitesPort import (
    ISatelliteAdapter, ISatellitesService
)

class SatelliteAdapter(ISatelliteAdapter):
    async def fetch(self) -> list[SatelliteRecord]:
        return []  # replace with real retrieval logic

class SatellitesService(ISatellitesService):
    def __init__(self, adapter: ISatelliteAdapter):
        self._adapter = adapter

    async def get_satellites(self) -> list[SatelliteRecord]:
        return await self._adapter.fetch()
```

## Caveats
- These are interface/port definitions only; calling the base methods raises `NotImplementedError`.
- Both APIs are `async`; consumers must `await` them in an async context.
