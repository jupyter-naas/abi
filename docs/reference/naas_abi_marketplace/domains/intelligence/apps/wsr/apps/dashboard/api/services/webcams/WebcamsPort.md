# WebcamsPort

## What it is
Interface contracts (ports) for a webcam/CCTV streaming process (`wsr:CCTVStreamingProcess`) backed by OpenWebcamDB. Defines the expected adapter and service APIs without implementation.

## Public API
- `class IWebcamAdapter`
  - `async fetch_list() -> list[CCTVCamera]`: Fetch the available cameras list.
  - `async fetch_stream(slug: str) -> StreamResult`: Fetch stream information for a given camera `slug`.

- `class IWebcamsService`
  - `property is_configured -> bool`: Whether the service is ready to operate (configuration present).
  - `async get_webcams() -> list[CCTVCamera]`: Return available cameras.
  - `async get_stream_url(slug: str) -> StreamResult`: Return stream information for a given camera `slug`.

## Configuration/Dependencies
- Imports models:
  - `ports.models.CCTVCamera`
  - `ports.models.StreamResult`
- All methods are `async` and are expected to be implemented by concrete classes.

## Usage
Minimal example implementing the interfaces:

```python
import asyncio
from ports.models import CCTVCamera, StreamResult
from naas_abi_marketplace.domains.intelligence.apps.wsr.apps.dashboard.api.services.webcams.WebcamsPort import (
    IWebcamAdapter, IWebcamsService
)

class DemoAdapter(IWebcamAdapter):
    async def fetch_list(self) -> list[CCTVCamera]:
        return []  # return real CCTVCamera instances

    async def fetch_stream(self, slug: str) -> StreamResult:
        raise NotImplementedError  # return a real StreamResult

class DemoService(IWebcamsService):
    def __init__(self, adapter: IWebcamAdapter, configured: bool = True):
        self._adapter = adapter
        self._configured = configured

    @property
    def is_configured(self) -> bool:
        return self._configured

    async def get_webcams(self) -> list[CCTVCamera]:
        return await self._adapter.fetch_list()

    async def get_stream_url(self, slug: str) -> StreamResult:
        return await self._adapter.fetch_stream(slug)

async def main():
    svc = DemoService(DemoAdapter())
    if svc.is_configured:
        cams = await svc.get_webcams()
        print(cams)

asyncio.run(main())
```

## Caveats
- These are abstract contracts only; calling methods on the base classes raises `NotImplementedError`.
- Requires an async runtime (`asyncio`) to call the methods.
