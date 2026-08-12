# EarthquakesPort

## What it is
- Defines async “port” interfaces for retrieving earthquake data.
- Specifies method signatures that return `list[EarthquakeFeature]`.

## Public API
- `class IEarthquakeAdapter`
  - `async fetch() -> list[EarthquakeFeature]`
    - Contract for an adapter that fetches earthquake features (e.g., from an external API).
- `class IEarthquakesService`
  - `async get_earthquakes() -> list[EarthquakeFeature]`
    - Contract for a service that returns earthquake features (typically using an adapter).

## Configuration/Dependencies
- Imports `EarthquakeFeature` from `ports.models`.
- Requires an async runtime (e.g., `asyncio`) to call `fetch()` / `get_earthquakes()`.

## Usage
```python
import asyncio
from naas_abi_marketplace.domains.intelligence.apps.wsr.apps.dashboard.api.services.earthquakes.EarthquakesPort import (
    IEarthquakeAdapter,
    IEarthquakesService,
)

class MyAdapter(IEarthquakeAdapter):
    async def fetch(self):
        return []  # list[EarthquakeFeature]

class MyService(IEarthquakesService):
    def __init__(self, adapter: IEarthquakeAdapter):
        self.adapter = adapter

    async def get_earthquakes(self):
        return await self.adapter.fetch()

async def main():
    service = MyService(MyAdapter())
    data = await service.get_earthquakes()
    print(data)

asyncio.run(main())
```

## Caveats
- Both interface methods raise `NotImplementedError` unless implemented by subclasses.
