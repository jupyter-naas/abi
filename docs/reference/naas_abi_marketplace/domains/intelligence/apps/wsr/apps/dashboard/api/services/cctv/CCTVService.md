# CCTVService

## What it is
- Async orchestrator for CCTV camera sources (adapters).
- Aggregates camera lists from multiple adapters with a static fallback.
- Provides an HLS/JPEG snapshot proxy with short TTL caching.

## Public API

### `class CCTVService(ICCTVService)`
**Purpose:** Fetch/merge camera data from adapters and proxy snapshot bytes.

- `__init__(self, adapters: list[ICCTVAdapter]) -> None`
  - Stores provided adapters.
  - Creates a static fallback adapter: `MideastAdapter()`.

- `async get_cameras(self) -> list[CCTVCamera]`
  - Concurrently calls `fetch()` on all configured adapters via `asyncio.gather`.
  - Flattens results into a single `list[CCTVCamera]`.
  - On any exception, logs a warning and returns the static fallback adapter’s `fetch()` result.

- `async proxy_snapshot(self, url: str) -> tuple[bytes, str]`
  - Returns `(content_bytes, content_type)` for a snapshot URL.
  - Uses a module-level `TTLCache` (4 seconds, max 500 entries) to cache responses per URL.

## Configuration/Dependencies
- **Async runtime:** Uses `asyncio` and async HTTP calls.
- **Caching:** `core.cache.TTLCache`
  - Module-level cache: `_snap_cache = TTLCache(ttl_seconds=4, max_size=500)`
- **HTTP client:** `core.http_client.get_client()`
  - Used to `GET`:
    - HLS playlists (`.m3u8`) with `timeout=5`
    - Snapshot/segment content with `timeout=6`
- **Models/ports:**
  - `ports.models.CCTVCamera`
  - `services.cctv.CCTVPort.ICCTVAdapter`, `ICCTVService`
- **Fallback adapter:** `services.cctv.adapters.mideast.MideastAdapter`

## Usage

```python
import asyncio
from naas_abi_marketplace.domains.intelligence.apps.wsr.apps.dashboard.api.services.cctv.CCTVService import CCTVService

# ICCTVAdapter instances must implement: async fetch() -> list[CCTVCamera]
async def main(adapters):
    svc = CCTVService(adapters=adapters)

    cameras = await svc.get_cameras()
    print(f"cameras: {len(cameras)}")

    content, content_type = await svc.proxy_snapshot("https://example.com/cam.jpg")
    print(content_type, len(content))

# asyncio.run(main(adapters=[...]))
```

## Caveats
- `get_cameras()` fails over to the static adapter if *any* exception occurs during dynamic adapter fetching.
- `proxy_snapshot()` supports `.m3u8` URLs by downloading the playlist, selecting the last non-comment line as the segment, and then fetching that segment.
- HLS playlist parsing is minimal (no variant playlist selection; last segment line is used).
- Snapshot responses are cached for ~4 seconds; content may lag behind the live feed within the TTL.
