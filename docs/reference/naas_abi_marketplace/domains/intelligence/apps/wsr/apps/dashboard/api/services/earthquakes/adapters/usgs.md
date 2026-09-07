# USGSAdapter

## What it is
- Async adapter that fetches earthquake data from the USGS GeoJSON “all day” feed.
- Filters results to earthquakes with magnitude **≥ 1.0**.
- Caches fetched results for **300 seconds** to reduce upstream calls.

## Public API
- `class USGSAdapter(IEarthquakeAdapter)`
  - `__init__(self) -> None`
    - Initializes an in-memory `TTLCache` with a 300s TTL.
  - `async fetch(self) -> list[EarthquakeFeature]`
    - Returns a cached list of `EarthquakeFeature` objects; fetches from USGS when cache is cold/expired.

## Configuration/Dependencies
- Upstream endpoint (fixed):
  - `https://earthquake.usgs.gov/earthquakes/feed/v1.0/summary/all_day.geojson`
- Dependencies (imported):
  - `core.cache.TTLCache` for caching.
  - `core.http_client.get_client()` providing an async HTTP client with `.get(...)`.
  - `ports.models.EarthquakeFeature` output model.
  - `services.earthquakes.EarthquakesPort.IEarthquakeAdapter` adapter interface.
- HTTP settings:
  - Request timeout: `8` seconds.
  - Uses `resp.raise_for_status()` to fail on non-2xx responses.

## Usage
```python
import asyncio
from naas_abi_marketplace.domains.intelligence.apps.wsr.apps.dashboard.api.services.earthquakes.adapters.usgs import USGSAdapter

async def main():
    adapter = USGSAdapter()
    quakes = await adapter.fetch()
    for q in quakes[:5]:
        print(q.id, q.mag, q.place, q.lat, q.lon, q.depth, q.time)

asyncio.run(main())
```

## Caveats
- GeoJSON coordinate order is assumed to be `[longitude, latitude, depth_km]`.
- If `geometry.coordinates` is missing, defaults to `[0, 0, 0]`.
- Only records with `properties.mag` present and `>= 1.0` are returned.
- `time` is set to `0` if missing from the feed.
