# `main` (NEXUS API entrypoint)

## What it is
- FastAPI application entrypoint for the NEXUS API.
- Builds (or patches) a FastAPI app with:
  - CORS + security headers middleware
  - API routes (including health and Ollama helpers)
  - Static asset mounts
  - Startup/shutdown lifecycle (DB init, seeding, background workers)
  - WebSocket wrapping via `init_websocket(...)`

## Public API
### Functions
- `create_app(app: FastAPI | None = None)`
  - Creates a new FastAPI app (when `app is None`) or patches an existing one.
  - Returns the final ASGI app **wrapped with WebSocket support** (via `init_websocket`).
  - Idempotent: caches the wrapped ASGI app in `app.state._nexus_asgi_app` and avoids re-patching via `app.state._nexus_api_patched`.

- `health_check() -> dict[str, str]`
  - Handler for `GET /health`.
  - Returns `{"status": "healthy", "service": "nexus-api"}`.

- `ollama_status()`
  - Handler for `GET /api/ollama/status`.
  - Returns `await get_ollama_status()`.

- `ollama_pull_model(model: str = "qwen3-vl:2b")`
  - Handler for `POST /api/ollama/pull`.
  - If Ollama is running: starts a background pull task and returns immediately.

- `ollama_ensure_ready(model: str = "qwen3-vl:2b")`
  - Handler for `POST /api/ollama/ensure-ready`.
  - Calls `ensure_ollama_ready(required_model=model)` and returns:
    - `{"ready": bool, "status": result}` where `ready` requires Ollama running and model available/pulled.

### Classes
- `SecurityHeadersMiddleware(BaseHTTPMiddleware)`
  - Adds security headers to HTTP responses when `settings.enable_security_headers` is true.
  - Skips adding headers for WebSocket upgrade requests (`/ws/...` or `Upgrade: websocket`).

### Module-level ASGI app
- `app`
  - Result of `create_app()`; used by Uvicorn/Gunicorn.

## Configuration/Dependencies
### Key dependencies
- FastAPI/Starlette (`FastAPI`, middleware, `StaticFiles`)
- Uvicorn (`uvicorn.run` in `__main__`)
- Internal services/config:
  - `settings`, `validate_settings_on_startup()`
  - `configure_logging()`
  - `init_db()` (DB initialization/migrations)
  - `register_service_exception_handlers(app)`
  - `start_chat_ingestion_consumer(app)` (started best-effort)
  - `init_websocket(app)` (wraps the ASGI app)
  - `api_router` mounted at `/api`
  - Ollama helpers: `get_ollama_status`, `ensure_ollama_ready`, `pull_model`, `is_ollama_running`

### Runtime behavior (startup)
- Logging is configured.
- Service registry is initialized (`initialize_nexus_service_registry()`).
- Settings are validated (`validate_settings_on_startup()`).
- Database init is awaited; failure raises and prevents startup.
- Optional demo seed: if `settings.auto_seed_demo_data` (defaulting to `True` if missing), calls `seed.ensure_seed_data()` when present.
- Applies configuration-driven seeds via `apply_configuration_seeds(...)`.
- Starts chat ingestion consumer (exceptions are logged, non-fatal).
- Prefetches the agent class registry in the background (non-fatal).

### Middleware and routing
- CORS origins: `app.state.abi_cors_origins` if present, else `[settings.frontend_url]`.
- Routes added:
  - `GET /health`
  - `GET /api/ollama/status`
  - `POST /api/ollama/pull`
  - `POST /api/ollama/ensure-ready`
  - plus `api_router` under `/api`
- Static mounts (if paths exist):
  - `/logos`, `/avatars`, `/organizations`
  - `/uploads` (directory is created if missing)

## Usage
### Run with Uvicorn (programmatic)
```python
import uvicorn
from naas_abi.apps.nexus.apps.api.app.main import app

uvicorn.run(app, host="0.0.0.0", port=9879)
```

### Create a new app explicitly
```python
from naas_abi.apps.nexus.apps.api.app.main import create_app

asgi_app = create_app()
```

### Patch an existing FastAPI app
```python
from fastapi import FastAPI
from naas_abi.apps.nexus.apps.api.app.main import create_app

base = FastAPI()
asgi_app = create_app(base)  # returns wrapped ASGI app
```

## Caveats
- `create_app(...)` returns the **wrapped** ASGI app from `init_websocket(app)`, not necessarily the original `FastAPI` instance you passed in.
- Startup will fail hard if `init_db()` raises `ConnectionError`.
- Security headers are skipped for WebSocket upgrade requests by design.
- When `settings.environment != "development"` and `settings.debug` is false, OpenAPI docs endpoints (`/docs`, `/redoc`) are disabled.
