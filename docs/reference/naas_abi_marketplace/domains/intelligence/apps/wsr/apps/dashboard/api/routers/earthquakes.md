# earthquakes (FastAPI router)

## What it is
- A FastAPI router exposing an HTTP endpoint to return **M≥1.0 earthquakes in the past 24 hours** (USGS), via `services.earthquakes.earthquake_service`.

## Public API
- `router: fastapi.APIRouter`
  - Router tagged as `["earthquakes"]`.
  - Registers the endpoint below.
- `get_earthquakes() -> fastapi.responses.JSONResponse`
  - **Route:** `GET /api/earthquakes`
  - Calls `await earthquake_service.get_earthquakes()`.
  - Returns a JSON array where each item is `q.model_dump(by_alias=True)`.
  - Sets header: `Cache-Control: public, max-age=300`.

## Configuration/Dependencies
- **FastAPI**
  - `APIRouter` for route definition.
  - `JSONResponse` for response formatting.
- **Service dependency**
  - `services.earthquakes.earthquake_service`
    - Must expose async `get_earthquakes()`.
    - Returned items must implement `model_dump(by_alias=True)` (e.g., Pydantic models).

## Usage
Minimal FastAPI app wiring:

```python
from fastapi import FastAPI
from naas_abi_marketplace.domains.intelligence.apps.wsr.apps.dashboard.api.routers.earthquakes import router

app = FastAPI()
app.include_router(router)
```

Call the endpoint:

```bash
curl http://localhost:8000/api/earthquakes
```

## Caveats
- If objects returned by `earthquake_service.get_earthquakes()` do not support `model_dump(by_alias=True)`, the endpoint will raise an error.
- Response caching is controlled via `Cache-Control: public, max-age=300` (5 minutes).
