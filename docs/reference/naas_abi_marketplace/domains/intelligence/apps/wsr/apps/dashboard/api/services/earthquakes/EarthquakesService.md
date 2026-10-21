# EarthquakesService

## What it is
- An async service that retrieves earthquake data via an injected adapter.
- Catches adapter errors, logs a warning, and returns a safe default (`[]`).

## Public API
- `class EarthquakesService(IEarthquakesService)`
  - `__init__(adapter: IEarthquakeAdapter) -> None`
    - Stores the adapter used to fetch earthquake data.
  - `async get_earthquakes() -> list[EarthquakeFeature]`
    - Fetches and returns a list of `EarthquakeFeature` from the adapter.
    - On any exception: logs a warning and returns an empty list.

## Configuration/Dependencies
- Depends on:
  - `IEarthquakeAdapter` (from `services.earthquakes.EarthquakesPort`) providing `async fetch()`.
  - `IEarthquakesService` interface (from `services.earthquakes.EarthquakesPort`).
  - `EarthquakeFeature` model (from `ports.models`).
  - `logging` for warning output.

## Usage
```python
import asyncio
from services.earthquakes.EarthquakesService import EarthquakesService

class DummyAdapter:
    async def fetch(self):
        return []  # should return list[EarthquakeFeature] in real usage

async def main():
    service = EarthquakesService(adapter=DummyAdapter())
    earthquakes = await service.get_earthquakes()
    print(earthquakes)

asyncio.run(main())
```

## Caveats
- Exceptions raised by the adapter are swallowed; `get_earthquakes()` returns `[]` and only logs a warning.
