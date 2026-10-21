# flights (FastAPI router)

## What it is
- A FastAPI router exposing HTTP endpoints for flight tracking data.
- Provides three GET endpoints returning JSON lists of flight objects sourced via `services.flights.flight_service`.

## Public API
- `router: fastapi.APIRouter`
  - Router tagged as `["flights"]`.

- `get_flights() -> fastapi.responses.JSONResponse`
  - `GET /api/flights`
  - Returns civil aviation flights from `flight_service.get_civil()`.
  - Sets `Cache-Control: public, max-age=30`.

- `get_military() -> fastapi.responses.JSONResponse`
  - `GET /api/military`
  - Returns military flights from `flight_service.get_military()`.
  - Sets `Cache-Control: public, max-age=60`.

- `get_mideast_aircraft() -> fastapi.responses.JSONResponse`
  - `GET /api/mideast-aircraft`
  - Returns theater aircraft flights from `flight_service.get_theater()`.
  - Sets `Cache-Control: public, max-age=45`.

## Configuration/Dependencies
- Depends on:
  - `fastapi.APIRouter`
  - `fastapi.responses.JSONResponse`
  - `services.flights.flight_service` with async methods:
    - `get_civil()`
    - `get_military()`
    - `get_theater()`
- Response serialization:
  - Each returned item is expected to support `model_dump(by_alias=True)` (typically a Pydantic model).

## Usage
```python
from fastapi import FastAPI
from naas_abi_marketplace.domains.intelligence.apps.wsr.apps.dashboard.api.routers import flights

app = FastAPI()
app.include_router(flights.router)
```

## Caveats
- Endpoints assume `flight_service` returns an iterable of objects implementing `model_dump(by_alias=True)`; otherwise responses will fail at serialization time.
- Cache headers are hard-coded per endpoint.
