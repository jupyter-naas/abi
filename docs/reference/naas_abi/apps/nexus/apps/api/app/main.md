# NEXUS API Main Application (`main.py`)

## What it is
- FastAPI application entry point for the NEXUS API.
- Wires together:
  - startup/lifespan initialization (logging, settings validation, DB init, seeding, Ollama status)
  - middleware (CORS + security headers)
  - routes (API router + health/Ollama endpoints)
  - static asset mounts
  - WebSocket support wrapping (via `init_websocket`)
- Provides a `create_app()` factory used both for standalone execution (uvicorn) and embedding into another FastAPI app.

## Public API
### Functions
- `create_app(app: FastAPI | None = None)`
  - Creates a new FastAPI app (when `app is None`) or patches an existing one.
  - Ensures middleware, routes, static mounts are registered once.
  - Returns an ASGI app wrapped with WebSocket support (`init_websocket(app)`).

### Middleware
- `SecurityHeadersMiddleware(BaseHTTPMiddleware)`
  - Adds security headers to HTTP responses when `settings.enable_security_headers` is enabled.
  - Skips adding headers for WebSocket upgrade requests (`/ws/` path or `Upgrade: websocket` header).

### Route handlers (registered via `_register_routes`)
- `GET /health` → `health_check()`
  - Returns `{"status": "healthy", "service": "nexus-api"}`.
- `GET /api/ollama/status` → `ollama_status()`
  - Returns current Ollama status via `get_ollama_status()`.
- `POST /api/ollama/pull` → `ollama_pull_model(model: str = "qwen3-vl:2b")`
  - If Ollama is running, starts `pull_model(model)` in a background task and returns immediately.
- `POST /api/ollama/ensure-ready` → `ollama_ensure_ready(model: str = "qwen3-vl:2b")`
  - Calls `ensure_ollama_ready(required_model=model)` and returns:
    - `ready`: `True` if Ollama is running and the model is available or was pulled
    - `status`: the full readiness result

## Configuration/Dependencies
- Settings sourced from `naas_abi.apps.nexus.apps.api.app.core.config`:
  - `settings` (used throughout)
  - `validate_settings_on_startup()` (called during startup)
- Database:
  - `init_db()` is awaited during startup; failure raises and prevents startup.
- Optional seeding:
  - If `settings.auto_seed_demo_data` is truthy (default `True` if missing), imports `naas_abi.apps.nexus.apps.api.seed` and awaits `ensure_seed_data()` if present/callable.
  - Applies config-driven org/workspace/user seeds via `apply_configuration_seeds(app.state.secret_service)`.
- Ollama integration:
  - Uses `ensure_ollama_ready`, `get_ollama_status`, and (when autostart disabled) `is_ollama_running` / `get_installed_models`.
  - Autostart gated by `settings.enable_ollama_autostart`.
  - Default required/pulled model referenced: `"qwen3-vl:2b"`.
- Middleware configuration:
  - CORS origins from `settings.cors_origins_list`.
  - Security headers controlled by:
    - `settings.enable_security_headers`
    - `settings.environment` (`"production"` enables HSTS and default CSP if no explicit CSP)
    - `settings.content_security_policy` (if provided)
- Static assets mounted if directories exist:
  - `/logos` from `.../public/logos`
  - `/avatars` from `.../public/avatars`
  - `/organizations` from `.../public/organizations`
  - `/uploads` from `.../uploads` (directory is created if missing)

## Usage
### Run with uvicorn (module executed directly)
```python
# main.py (already includes __main__ runner)
# python -m naas_abi.apps.nexus.apps.api.app.main
```

### Create an ASGI app (recommended for uvicorn/gunicorn)
```python
from naas_abi.apps.nexus.apps.api.app.main import create_app

app = create_app()
```

### Patch an existing FastAPI app
```python
from fastapi import FastAPI
from naas_abi.apps.nexus.apps.api.app.main import create_app

base_app = FastAPI()
asgi_app = create_app(base_app)  # returns ASGI wrapper (WebSocket-enabled)
```

## Caveats
- When patching an existing app (`create_app(existing_app)`), startup/shutdown are added via event handlers; when creating a new app, lifespan is used. This affects how initialization hooks are attached.
- `create_app()` returns the WebSocket-wrapped ASGI app (from `init_websocket(app)`), not necessarily the raw `FastAPI` instance.
- Security headers are intentionally skipped for WebSocket upgrade requests.
- Startup will fail hard if `init_db()` raises `ConnectionError` (API will not start without DB connection).
