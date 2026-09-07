# OpenSkyAdapter

## What it is
- An async flight-tracking adapter implementing `IFlightAdapter`.
- Primary data source: OpenSky Network (`/api/states/all`) with prioritized authentication.
- Fallback data source: `airplanes.live` tiled point queries (no auth), merged and de-duplicated.
- Includes a 30-second TTL cache for flight state responses.

## Public API
- `class OpenSkyAdapter(IFlightAdapter)`
  - `__init__() -> None`
    - Initializes:
      - a `TTLCache` (30s) for fetched flights
      - OAuth2 token storage and expiry tracking
  - `async fetch() -> list[FlightState]`
    - Returns cached flight states when available; otherwise performs a network fetch (OpenSky, then fallback).

## Configuration/Dependencies
- Settings (from `settings.settings`):
  - OAuth2 client credentials (preferred when available):
    - `settings.opensky_client_id`
    - `settings.opensky_client_secret`
  - Legacy basic auth (used if OAuth2 is not configured):
    - `settings.opensky_username`
    - `settings.opensky_password`
- External dependencies:
  - `core.http_client.get_client()` providing an async HTTP client with `.get()` / `.post()`, `.json()`, `.raise_for_status()`, and `.is_success`.
  - `core.cache.TTLCache` providing `get_or_fetch(key, coro_factory)`.
  - `ports.models.FlightState` model used for normalized flight state output.
- External services:
  - OpenSky states endpoint: `https://opensky-network.org/api/states/all`
  - OpenSky OAuth2 token endpoint: `https://auth.opensky-network.org/.../token`
  - Fallback tiles: `https://api.airplanes.live/v2/point/{lat}/{lon}/{radius}`
- Behavior notes:
  - OAuth2 token is cached in-memory until expiry (`expires_in - 60s`).
  - Fallback tiles cover 8 predefined global regions and results are de-duplicated by `icao24`.

## Usage
```python
import asyncio
from naas_abi_marketplace.domains.intelligence.apps.wsr.apps.dashboard.api.services.flights.adapters.opensky import OpenSkyAdapter

async def main():
    adapter = OpenSkyAdapter()
    flights = await adapter.fetch()
    print(len(flights))
    if flights:
        f = flights[0]
        print(f.icao24, f.callsign, f.lat, f.lon)

asyncio.run(main())
```

## Caveats
- `fetch()` returns cached results for up to 30 seconds (may not reflect real-time changes within that window).
- If OpenSky returns an empty `states` list or request fails, the adapter falls back to `airplanes.live` tiles.
- Fallback altitude/velocity units are converted:
  - altitude: feet → meters
  - ground speed: knots → m/s
- Flights with missing latitude/longitude are skipped.
