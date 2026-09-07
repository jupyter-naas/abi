# CCTVPort

## What it is
Defines interface contracts (ports) for a CCTV streaming process:
- `ICCTVAdapter`: contract for source adapters that fetch camera data.
- `ICCTVService`: contract for the service layer used by routers.

## Public API
- `class ICCTVAdapter`
  - `async fetch() -> list[CCTVCamera]`: Fetch and return a list of cameras from a single CCTV data source.

- `class ICCTVService`
  - `async get_cameras() -> list[CCTVCamera]`: Return the aggregated list of cameras to callers (e.g., routers).
  - `async proxy_snapshot(url: str) -> tuple[bytes, str]`: Fetch/proxy a snapshot from `url`, returning `(content_bytes, content_type)`.

## Configuration/Dependencies
- Depends on `ports.models.CCTVCamera` for the camera model type.

## Usage
```python
from naas_abi_marketplace.domains.intelligence.apps.wsr.apps.dashboard.api.services.cctv.CCTVPort import (
    ICCTVAdapter, ICCTVService
)
from ports.models import CCTVCamera

class MyAdapter(ICCTVAdapter):
    async def fetch(self) -> list[CCTVCamera]:
        return []  # implement source-specific fetch

class MyService(ICCTVService):
    def __init__(self, adapter: ICCTVAdapter):
        self.adapter = adapter

    async def get_cameras(self) -> list[CCTVCamera]:
        return await self.adapter.fetch()

    async def proxy_snapshot(self, url: str) -> tuple[bytes, str]:
        return b"", "image/jpeg"  # implement proxying
```

## Caveats
- These are abstract contracts only; all methods raise `NotImplementedError` until implemented.
