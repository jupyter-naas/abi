# `main` (WSR FastAPI Service)

## What it is
- FastAPI application entrypoint for the WSR Data API (“BFO-grounded geospatial intelligence data service”).
- Provides:
  - Application lifespan hooks to initialize and close a shared HTTP client.
  - CORS middleware configuration.
  - Inclusion of multiple domain routers.
  - A `/health` endpoint.

## Public API
- **`app: fastapi.FastAPI`**
  - Preconfigured FastAPI application instance (title, description, version, lifespan, CORS, routers).
- **`lifespan(app: FastAPI)`**
  - Async context manager used as the FastAPI lifespan handler:
    - Startup: `init_client()`
    - Shutdown: `close_client()`
- **`health()`** (`GET /health`)
  - Returns a static health payload: `{"status": "ok", "service": "wsr-backend"}`

## Configuration/Dependencies
- **FastAPI / ASGI**
  - `fastapi.FastAPI`
- **CORS**
  - `fastapi.middleware.cors.CORSMiddleware`
  - Configured with:
    - `allow_origins = settings.allowed_origins`
    - `allow_credentials = False`
    - `allow_methods = ["GET"]`
    - `allow_headers = ["*"]`
- **HTTP client lifecycle**
  - `core.http_client.init_client()` on startup
  - `core.http_client.close_client()` on shutdown
- **Routers included**
  - `routers.flights.router`
  - `routers.satellites.router`
  - `routers.earthquakes.router`
  - `routers.news.router`
  - `routers.conflict.router`
  - `routers.cctv.router`
  - `routers.webcams.router`
- **Settings**
  - `settings.allowed_origins` controls CORS allowed origins.

## Usage
Run with an ASGI server (e.g., `uvicorn`):

```python
import uvicorn

uvicorn.run(
    "naas_abi_marketplace.domains.intelligence.apps.wsr.apps.dashboard.api.main:app",
    host="0.0.0.0",
    port=8000,
)
```

Health check:

```python
import requests

print(requests.get("http://localhost:8000/health").json())
```

## Caveats
- CORS is restricted to `settings.allowed_origins`.
- CORS allows only `GET` methods (`allow_methods=["GET"]`).
