# AirplanesLiveAdapter

## What it is
- An async flight-data adapter for the **airplanes.live** API focused on the Middle East theater.
- It queries **three predefined regions concurrently**, merges results, and **deduplicates aircraft by `icao24`**.
- Results are **cached for 45 seconds** to reduce API load.

## Public API
- `class AirplanesLiveAdapter(IFlightAdapter)`
  - `__init__(self) -> None`
    - Initializes a 45-second TTL cache for fetched flight states.
  - `async fetch(self) -> list[FlightState]`
    - Returns a cached list of `FlightState` objects; fetches fresh data when cache expires.

## Configuration/Dependencies
- External services:
  - HTTP GET to `https://api.airplanes.live/v2/point/{lat}/{lon}/{radius}`
  - Uses headers: `{"User-Agent": "WSR-Intel/1.0"}`
- Internal dependencies:
  - `core.cache.TTLCache` (used with `ttl_seconds=45`)
  - `core.http_client.get_client()` (must provide an async `.get(...)` returning an object with:
    - `.is_success`
    - `.json()`)
  - `ports.models.FlightState` (output model)
  - `services.flights.FlightsPort.IFlightAdapter` (interface implemented)
- Query strategy:
  - Regions queried (lat, lon, radius):
    - (32, 53, 500), (32, 35, 300), (25, 52, 200)
  - Concurrency via `asyncio.gather`
- Unit conversions:
  - Altitude: feet → meters (`0.3048`)
  - Ground speed: knots → m/s (`0.514444`)

## Usage
```python
import asyncio
from naas_abi_marketplace.domains.intelligence.apps.wsr.apps.dashboard.api.services.flights.adapters.airplanes_live import AirplanesLiveAdapter

async def main():
    adapter = AirplanesLiveAdapter()
    flights = await adapter.fetch()
    print(len(flights))
    if flights:
        print(flights[0])

asyncio.run(main())
```

## Caveats
- Network/parse errors and non-success HTTP responses are **silently swallowed** and yield `[]` for that region (or overall if all fail).
- Aircraft entries without `lat`/`lon` are skipped.
- `onGround` is always set to `False` (no ground-state inference here).
- Deduplication uses `icao24` and keeps the **first** occurrence across region results.
