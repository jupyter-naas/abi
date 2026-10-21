# cctv (FastAPI router)

## What it is
- A FastAPI router exposing an HTTP interface for CCTV camera discovery and snapshot/HLS proxying.
- Provides:
  - A merged camera list endpoint.
  - A short-TTL proxy endpoint for image/HLS URLs.

## Public API
- `router: fastapi.APIRouter`
  - Tagged as `["cctv"]`.

- `get_cctv() -> fastapi.responses.JSONResponse`
  - **Route:** `GET /api/cctv`
  - Returns a list of cameras from `cctv_service.get_cameras()`.
  - Response headers:
    - `Cache-Control: public, max-age=300`
  - Serializes each camera via `model_dump(by_alias=True)`.

- `get_cctv_snapshot(url: str) -> fastapi.responses.Response`
  - **Route:** `GET /api/cctv/snapshot?url=...`
  - Proxies a source image or HLS URL via `cctv_service.proxy_snapshot(url)`.
  - Success response:
    - Body: proxied content
    - `media_type`: content-type returned by the service
    - Headers:
      - `Cache-Control: public, max-age=4`
      - `Access-Control-Allow-Origin: *`
  - Error response:
    - HTTP `502`
    - JSON: `{"error": "<exception message>"}`

## Configuration/Dependencies
- **FastAPI**:
  - `APIRouter`, `Query`
  - `JSONResponse`, `Response`
- **Service dependency**:
  - `services.cctv.cctv_service` must provide:
    - `await cctv_service.get_cameras()`
    - `await cctv_service.proxy_snapshot(url) -> (body, content_type)`
- **Logging**:
  - Uses module logger `logging.getLogger(__name__)`.

## Usage
Minimal integration into a FastAPI app:

```python
from fastapi import FastAPI
from naas_abi_marketplace.domains.intelligence.apps.wsr.apps.dashboard.api.routers.cctv import router as cctv_router

app = FastAPI()
app.include_router(cctv_router)
```

Example requests:
- `GET /api/cctv`
- `GET /api/cctv/snapshot?url=https://example.com/cam.jpg`

## Caveats
- `/api/cctv/snapshot` proxies arbitrary URLs provided by clients; failures return `502` with the exception message.
- Snapshot responses are explicitly cacheable for **4 seconds** and allow cross-origin access (`Access-Control-Allow-Origin: *`).
