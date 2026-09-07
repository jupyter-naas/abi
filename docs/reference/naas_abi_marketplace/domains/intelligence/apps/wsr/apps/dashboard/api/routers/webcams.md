# webcams (FastAPI router)

## What it is
A FastAPI router that exposes two endpoints backed by `services.webcams.webcam_service`:

- List webcams from OpenWebcamDB (cached via HTTP headers).
- Resolve a webcam stream URL by slug (cached via HTTP headers).

## Public API
- `router: fastapi.APIRouter`
  - Tagged as `["webcams"]`.

- `get_webcams() -> fastapi.responses.JSONResponse`
  - **Route:** `GET /api/webcams`
  - Returns a list of webcams (`model_dump(by_alias=True)` per item).
  - Adds header: `Cache-Control: public, max-age=3600`.
  - Errors:
    - `503` if `OPENWEBCAMDB_API_KEY` is not configured.

- `get_webcam_stream(slug: str) -> fastapi.responses.JSONResponse`
  - **Route:** `GET /api/webcams/stream`
  - **Query param:** `slug` (required; described as “OpenWebcamDB webcam slug”)
  - Returns resolved stream data (`result.model_dump()`).
  - Errors:
    - `503` if `OPENWEBCAMDB_API_KEY` is not configured.
    - `400` if `slug` is missing/empty.
    - `404` if `webcam_service.get_stream_url(slug)` raises `ValueError`.
    - `502` for any other exception.

## Configuration/Dependencies
- Depends on `services.webcams.webcam_service`, which must expose:
  - `is_configured: bool` (used to check `OPENWEBCAMDB_API_KEY` configuration)
  - `async get_webcams()`
  - `async get_stream_url(slug: str)`

- FastAPI dependencies:
  - `fastapi.APIRouter`, `fastapi.HTTPException`, `fastapi.Query`
  - `fastapi.responses.JSONResponse`

## Usage
Minimal integration into a FastAPI app:

```python
from fastapi import FastAPI
from naas_abi_marketplace.domains.intelligence.apps.wsr.apps.dashboard.api.routers.webcams import router as webcams_router

app = FastAPI()
app.include_router(webcams_router)
```

Example requests:
- `GET /api/webcams`
- `GET /api/webcams/stream?slug=<openwebcamdb-slug>`

## Caveats
- The endpoints return `503` unless `webcam_service.is_configured` is `True` (expected to reflect `OPENWEBCAMDB_API_KEY` presence).
- Caching is communicated only via `Cache-Control` headers on `/api/webcams`; the module docstring mentions caching for stream resolution, but the `/api/webcams/stream` handler does not set caching headers.
