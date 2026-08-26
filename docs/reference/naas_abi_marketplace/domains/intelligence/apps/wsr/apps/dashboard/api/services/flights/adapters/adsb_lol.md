# ADSBLolAdapter

## What it is
- An async flight data adapter that fetches **global military aircraft** positions from **ADSB.lol** with a **fallback** to **airplanes.live** (same response schema).
- Normalizes API responses into a list of `FlightState` objects.
- Uses a 60-second TTL cache to limit upstream calls.

## Public API
- `class ADSBLolAdapter(IFlightAdapter)`
  - `__init__() -> None`
    - Initializes an internal `TTLCache` with `ttl_seconds=60`.
  - `async fetch() -> list[FlightState]`
    - Returns cached results for key `"military"` or fetches fresh data via `_fetch()`.

## Configuration/Dependencies
- External endpoints:
  - Primary: `https://api.adsb.lol/v2/mil`
  - Fallback: `https://api.airplanes.live/v2/mil`
- HTTP:
  - Uses `core.http_client.get_client()` and performs `GET` with:
    - `headers={"User-Agent": "WSR-Intel/1.0 (geospatial-intelligence-platform)"}`
    - `timeout=10`
- Caching:
  - `core.cache.TTLCache` (typed as `TTLCache[list[FlightState]]`) with 60s TTL.
- Models/ports:
  - `ports.models.FlightState`
  - `services.flights.FlightsPort.IFlightAdapter`

## Usage
```python
import asyncio
from naas_abi_marketplace.domains.intelligence.apps.wsr.apps.dashboard.api.services.flights.adapters.adsb_lol import (
    ADSBLolAdapter,
)

async def main():
    adapter = ADSBLolAdapter()
    flights = await adapter.fetch()
    for f in flights[:5]:
        print(f.icao24, f.callsign, f.lat, f.lon, f.altitude)

asyncio.run(main())
```

## Caveats
- Missing `lat`/`lon` entries are skipped.
- All returned flights are marked:
  - `onGround=False`
  - `isMilitary=True`
- Altitude parsing:
  - `alt_baro` is treated as **feet** and converted to meters; non-numeric values become `0.0`.
- Speed parsing:
  - `gs` is treated as **knots** and converted to m/s; missing values become `0`.
- Errors are swallowed:
  - If both primary and fallback requests fail or return no data, `fetch()` returns `[]`.
