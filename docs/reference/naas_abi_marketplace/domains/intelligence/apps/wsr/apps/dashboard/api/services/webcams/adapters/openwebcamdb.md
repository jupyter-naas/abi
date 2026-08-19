# OpenWebcamDBAdapter

## What it is
An adapter for the OpenWebcamDB API that:
- Fetches a cached list of webcams (`GET /webcams`, 1 page × 50, cached 1 hour).
- Resolves a cached stream URL for a specific webcam (`GET /webcams/{slug}`, cached 30 minutes).
- Requires `OPENWEBCAMDB_API_KEY`; returns an empty list when missing.

## Public API
### Class: `OpenWebcamDBAdapter(IWebcamAdapter)`
- `__init__()`
  - Initializes in-memory TTL caches:
    - List cache: 3600s
    - Stream cache: 1800s
- `async fetch_list() -> list[CCTVCamera]`
  - Returns up to 50 webcams (page 1).
  - Uses 1-hour cache.
  - Returns `[]` if `settings.openwebcamdb_api_key` is not set.
- `async fetch_stream(slug: str) -> StreamResult`
  - Resolves the stream URL for a webcam slug.
  - Uses 30-minute cache.
  - Raises on HTTP errors (`raise_for_status`) and if `stream_url` is missing.

### Functions (module-level)
- `_youtube_video_id(url: str) -> str | None`
  - Extracts a YouTube video ID from common YouTube URL formats.
- `_resolve_embed_url(raw: str, stream_type: str) -> StreamResult`
  - Returns a `StreamResult` with a YouTube embed URL when `stream_type == "youtube"` or a YouTube ID is detected.

## Configuration/Dependencies
- **Settings**
  - `settings.openwebcamdb_api_key` (derived from `OPENWEBCAMDB_API_KEY`)
    - Used to build `Authorization: Bearer <key>` header.
    - If unset/empty, `fetch_list()` returns `[]`.
- **HTTP**
  - `core.http_client.get_client()` must provide an async client with `.get(...)` returning a response supporting:
    - `.is_success`, `.json()`, `.raise_for_status()`
- **Caching**
  - `core.cache.TTLCache` with `get_or_fetch(key, coroutine_factory)`
- **Models/Ports**
  - `ports.models.CCTVCamera`, `ports.models.StreamResult`
  - `services.webcams.WebcamsPort.IWebcamAdapter`

## Usage
```python
import asyncio
from naas_abi_marketplace.domains.intelligence.apps.wsr.apps.dashboard.api.services.webcams.adapters.openwebcamdb import (
    OpenWebcamDBAdapter,
)

async def main():
    adapter = OpenWebcamDBAdapter()

    cams = await adapter.fetch_list()
    print(f"Got {len(cams)} webcams")
    if not cams:
        return

    slug = cams[0].slug
    stream = await adapter.fetch_stream(slug)
    print(stream.type, stream.url)

asyncio.run(main())
```

## Caveats
- Only the first page is fetched (`per_page=50`, `page=1`).
- `fetch_list()` silently returns `[]` on non-success HTTP responses.
- `fetch_stream()` raises exceptions on HTTP errors and when `stream_url` is absent.
- Stream results are always returned with `type="youtube"` (including non-YouTube raw URLs).
