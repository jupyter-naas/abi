# satellites (FastAPI router)

## What it is
- A FastAPI router that exposes an HTTP endpoint to retrieve active satellite TLE records (CelesTrak) via `satellite_service`.

## Public API
- `router: fastapi.APIRouter`
  - Router tagged as `["satellites"]`.
- `get_satellites() -> fastapi.responses.JSONResponse`
  - **Route:** `GET /api/satellites`
  - **Behavior:**
    - Awaits `satellite_service.get_satellites()`.
    - Serializes each returned item using `.model_dump()`.
    - Returns a `JSONResponse` with `Cache-Control: public, max-age=3600`.

## Configuration/Dependencies
- **FastAPI**
  - `fastapi.APIRouter`
  - `fastapi.responses.JSONResponse`
- **Service dependency**
  - `services.satellites.satellite_service` must provide an async `get_satellites()` returning iterable items that implement `.model_dump()`.

## Usage
Mount the router in a FastAPI app:

```python
from fastapi import FastAPI
from naas_abi_marketplace.domains.intelligence.apps.wsr.apps.dashboard.api.routers.satellites import router

app = FastAPI()
app.include_router(router)
```

Call the endpoint:

- `GET /api/satellites`

## Caveats
- Items returned by `satellite_service.get_satellites()` must implement `.model_dump()` (commonly Pydantic models) or serialization will fail.
- Responses are explicitly cacheable for up to 1 hour via `Cache-Control: public, max-age=3600`.
