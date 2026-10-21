# WebcamsService

## What it is
- Orchestrator service for CCTV/webcam listings and stream URLs via an injected adapter (OpenWebcamDB).
- Implements `IWebcamsService` and delegates all network/data access to an `IWebcamAdapter`.

## Public API
- **Class `WebcamsService(adapter: IWebcamAdapter)`**
  - `is_configured: bool` (property)
    - `True` if `settings.openwebcamdb_api_key` is set (truthy); otherwise `False`.
  - `async get_webcams() -> list[CCTVCamera]`
    - Returns a list of available cameras by calling `adapter.fetch_list()`.
  - `async get_stream_url(slug: str) -> StreamResult`
    - Returns stream details for a camera slug by calling `adapter.fetch_stream(slug)`.

## Configuration/Dependencies
- **Depends on**:
  - `settings.openwebcamdb_api_key` (used by `is_configured`).
  - `IWebcamAdapter` with methods:
    - `fetch_list() -> list[CCTVCamera]` (async)
    - `fetch_stream(slug: str) -> StreamResult` (async)
  - Models:
    - `CCTVCamera`
    - `StreamResult`

## Usage
```python
import asyncio
from services.webcams.WebcamsService import WebcamsService

# Provide a concrete IWebcamAdapter implementation in your app.
adapter = ...  # must implement async fetch_list() and fetch_stream(slug)

async def main():
    svc = WebcamsService(adapter)
    if not svc.is_configured:
        raise RuntimeError("OpenWebcamDB API key is not configured")

    cameras = await svc.get_webcams()
    stream = await svc.get_stream_url(slug="some-camera-slug")
    print(len(cameras), stream)

asyncio.run(main())
```

## Caveats
- All data retrieval methods are `async`; they must be awaited inside an event loop.
- `is_configured` only checks for presence of an API key; it does not validate connectivity or credentials.
