# LondonAdapter

## What it is
- Async adapter for **TfL JamCam** (public London traffic cameras) that fetches camera metadata from `https://api.tfl.gov.uk/Place/Type/JamCam`.
- Filters and maps TfL records into `CCTVCamera` models.
- Uses an in-memory TTL cache (5 minutes) to reduce request frequency.

## Public API
- `class LondonAdapter(ICCTVAdapter)`
  - `__init__()`: Initializes an internal `TTLCache[list[CCTVCamera]]` with `ttl_seconds=300`.
  - `async fetch() -> list[CCTVCamera]`: Returns cached cameras or fetches from TfL and caches the result.

## Configuration/Dependencies
- **Settings**
  - `settings.tfl_app_key`: Optional API key. If set (non-empty after `.strip()`), sent as `app_key` query parameter.
- **Dependencies**
  - `core.cache.TTLCache`: Provides `get_or_fetch(cache_key, fetch_coroutine)`.
  - `core.http_client.get_client()`: Returns an async HTTP client with `.get(...)`.
  - `ports.models.CCTVCamera`: Output model for each camera.
  - `services.cctv.CCTVPort.ICCTVAdapter`: Adapter interface implemented by this class.
- **HTTP**
  - URL: `https://api.tfl.gov.uk/Place/Type/JamCam`
  - Timeout: `15` seconds
  - Header: `User-Agent: WSR-Intel/1.0 (geospatial-intelligence-platform)`

## Usage
```python
import asyncio
from naas_abi_marketplace.domains.intelligence.apps.wsr.apps.dashboard.api.services.cctv.adapters.london import LondonAdapter

async def main():
    adapter = LondonAdapter()
    cameras = await adapter.fetch()
    print(f"Fetched {len(cameras)} cameras")
    if cameras:
        print(cameras[0])

asyncio.run(main())
```

## Caveats
- Returns `[]` if the TfL HTTP response is not successful (`resp.is_success` is false).
- Skips cameras when:
  - `lat`/`lon` is missing,
  - `additionalProperties.available` is `"false"` (case-insensitive),
  - `additionalProperties.imageUrl` is missing/empty.
- `videoUrl` is set to the same value as `imageUrl`, while `type` is set to `"hls"` (as implemented).
