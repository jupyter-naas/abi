# MideastAdapter

## What it is
A Middle East/theater CCTV adapter that returns a hardcoded, curated list of confirmed-live camera streams (verified February 2026).

## Public API
- `class MideastAdapter(ICCTVAdapter)`
  - `async fetch() -> list[CCTVCamera]`: Returns the curated in-module camera list (`_CAMERAS`).

## Configuration/Dependencies
- Depends on:
  - `ports.models.CCTVCamera`: camera data model used for entries.
  - `services.cctv.CCTVPort.ICCTVAdapter`: interface implemented by the adapter.
- Configuration:
  - None at runtime; camera entries are statically defined in `_CAMERAS`.

## Usage
```python
import asyncio
from naas_abi_marketplace.domains.intelligence.apps.wsr.apps.dashboard.api.services.cctv.adapters.mideast import (
    MideastAdapter,
)

async def main():
    adapter = MideastAdapter()
    cameras = await adapter.fetch()
    for cam in cameras:
        print(cam.id, cam.name, cam.country, cam.videoUrl or cam.imageUrl)

asyncio.run(main())
```

## Caveats
- `fetch()` returns a static list; it performs no network checks or discovery.
- Some entries may provide `videoUrl` only, `imageUrl` only, or leave one of them blank depending on the source.
