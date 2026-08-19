# conflict (Conflict events router)

## What it is
- A FastAPI router that exposes an HTTP endpoint returning a list of conflict events.
- Serves as the `wsr:ConflictZoneLoadingProcess` HTTP interface.

## Public API
- `router: fastapi.APIRouter`
  - Router instance tagged with `["conflict"]`.
- `get_conflict_events() -> fastapi.responses.JSONResponse`
  - **Route:** `GET /api/conflict-events`
  - **Behavior:**
    - Calls `conflict_service.get_events()`
    - Serializes each event via `e.model_dump()`
    - Returns JSON with `Cache-Control: public, max-age=86400` (24 hours)

## Configuration/Dependencies
- **FastAPI**
  - `fastapi.APIRouter`
  - `fastapi.responses.JSONResponse`
- **Service dependency**
  - `services.conflict.conflict_service`
    - Must expose `get_events()` returning an iterable of objects that implement `model_dump()`.

## Usage
```python
from fastapi import FastAPI
from naas_abi_marketplace.domains.intelligence.apps.wsr.apps.dashboard.api.routers.conflict import router as conflict_router

app = FastAPI()
app.include_router(conflict_router)
```

## Caveats
- Serialization requires each event object to provide `.model_dump()`; otherwise the endpoint will fail.
- Responses are cacheable by clients/proxies for up to 24 hours due to the `Cache-Control` header.
