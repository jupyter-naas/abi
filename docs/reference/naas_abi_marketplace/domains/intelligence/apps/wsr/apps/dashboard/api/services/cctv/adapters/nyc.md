# NYCAdapter

## What it is
- An async CCTV adapter that pulls New York City traffic camera metadata from the 511NY.org API.
- Filters cameras to a Manhattan + surrounding boroughs bounding box, excludes disabled/blocked entries, requires a `VideoUrl`, and caps results at 150.
- Caches results for 5 minutes.

## Public API
- `class NYCAdapter(ICCTVAdapter)`
  - `__init__(self) -> None`
    - Initializes an in-memory TTL cache (300 seconds).
  - `async fetch(self) -> list[CCTVCamera]`
    - Returns a cached list of cameras; refreshes via `_fetch` when cache is expired/missing.

## Configuration/Dependencies
- External API endpoint:
  - `https://511ny.org/api/getcameras?key=&format=json`
- Bounding box filter (module constant `_BOUNDS`):
  - lat: `40.60`–`40.90`
  - lon: `-74.05`–`-73.70`
- Dependencies (imported):
  - `core.cache.TTLCache` (used for 300s caching)
  - `core.http_client.get_client()` (HTTP client with async `.get()`)
  - `ports.models.CCTVCamera` (output model)
  - `services.cctv.CCTVPort.ICCTVAdapter` (adapter interface)
- Network behavior:
  - HTTP GET with `timeout=8`
  - On non-success response: returns `[]`

## Usage
```python
import asyncio
from naas_abi_marketplace.domains.intelligence.apps.wsr.apps.dashboard.api.services.cctv.adapters.nyc import NYCAdapter

async def main():
    adapter = NYCAdapter()
    cameras = await adapter.fetch()
    print(len(cameras))
    if cameras:
        print(cameras[0])

asyncio.run(main())
```

## Caveats
- Results are limited to:
  - Cameras within the hardcoded bounding box.
  - Cameras that are not `Disabled` and not `Blocked`.
  - Cameras with a non-empty `VideoUrl`.
  - A maximum of 150 cameras per fetch.
- On HTTP failure (non-success status), the adapter returns an empty list (no exception raised here).
