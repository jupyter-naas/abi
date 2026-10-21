# CelesTrakAdapter

## What it is
- An async adapter that fetches the **active satellite** TLE catalog from CelesTrak and returns it as a list of `SatelliteRecord`.
- Uses an in-memory TTL cache (1 hour) to avoid frequent upstream requests.

Source URL:
- `https://celestrak.org/NORAD/elements/gp.php?GROUP=active&FORMAT=TLE`

## Public API
- `class CelesTrakAdapter(ISatelliteAdapter)`
  - `__init__(self) -> None`
    - Creates a `TTLCache` with `ttl_seconds=3600`.
  - `async fetch(self) -> list[SatelliteRecord]`
    - Returns cached satellite records under key `"satellites"` or fetches from CelesTrak if cache expired/missing.

## Configuration/Dependencies
- Caching
  - `core.cache.TTLCache` with TTL set to 3600 seconds.
- HTTP
  - `core.http_client.get_client()` used to perform `GET` to the CelesTrak endpoint.
  - Request timeout: `30` seconds.
  - Calls `resp.raise_for_status()` to enforce non-error HTTP status.
- Models / Ports
  - `ports.models.SatelliteRecord` (constructed as `SatelliteRecord(name=..., line1=..., line2=...)`).
  - Implements `services.satellites.SatellitesPort.ISatelliteAdapter`.

## Usage
```python
import asyncio
from naas_abi_marketplace.domains.intelligence.apps.wsr.apps.dashboard.api.services.satellites.adapters.celestrak import (
    CelesTrakAdapter,
)

async def main():
    adapter = CelesTrakAdapter()
    records = await adapter.fetch()
    print(len(records))
    if records:
        print(records[0])

asyncio.run(main())
```

## Caveats
- Parsing is strict in 3-line blocks: `name`, then a line starting with `"1 "`, then a line starting with `"2 "`.
  - If a 3-line block doesn’t match this pattern, it is skipped (the loop still advances by 3).
- Cache key is fixed (`"satellites"`); all calls share the same cached dataset within the adapter instance.
- Requires an async runtime; `fetch()` must be awaited.
