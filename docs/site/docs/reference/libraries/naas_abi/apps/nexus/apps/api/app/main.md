# `main` (NEXUS API entrypoint)

## What it is
- FastAPI application entrypoint for the NEXUS API.
- Creates (or patches) a FastAPI app with:
  - Lifespan/startup tasks (DB init, seeds, background sync/warmups)
  - Middleware stack (CORS, settings cache, security headers, tracing, etc.)
  - HTTP routes (health, Ollama helpers, app HTML/preview/remote apps, provider logos)
  - Static asset serving (logos, avatars, organizations, uploads)
  - WebSocket wrapping via `init_websocket(...)`
- Exposes a module-level ASGI app (`app`) for Uvicorn/Gunicorn.

## Public API

### Module-level objects
- `app`
  - The ASGI application returned by `create_app()` (already wrapped by `init_websocket`).

### Functions
- `create_app(app: FastAPI | None = None)`
  - Creates a new `FastAPI` app when `app is None`, otherwise patches the passed app.
  - Applies middleware, routes, static mounts, and exception handlers once (guarded by `app.state._nexus_api_patched`).
  - Returns the WebSocket-wrapped ASGI app from `init_websocket(app)`.
  - Caches the returned ASGI app in `app.state._nexus_asgi_app` to avoid double-wrapping.

- `health_check() -> dict[str, str]`
  - Handler for `GET /health`.
  - Returns `{"status": "healthy", "service": "nexus-api"}`.

- `ollama_status()`
  - Handler for `GET /api/ollama/status`.
  - Returns `await get_ollama_status()`.
  - Route requires an authenticated user (`get_current_user_required` dependency).

- `ollama_pull_model(model: str = DEFAULT_MODEL)`
  - Handler for `POST /api/ollama/pull`.
  - If Ollama is not running: returns `{"success": False, "error": "Ollama is not running"}`.
  - Otherwise starts `pull_model(model)` in a background task and returns immediately.
  - Route requires superadmin (`require_superadmin` dependency).

- `ollama_ensure_ready(model: str = DEFAULT_MODEL)`
  - Handler for `POST /api/ollama/ensure-ready`.
  - Calls `ensure_ollama_ready(required_model=model)` and returns:
    - `{"ready": bool, "status": result}`
  - Route requires superadmin (`require_superadmin` dependency).

### Classes
- `SecurityHeadersMiddleware(BaseHTTPMiddleware)`
  - Adds security-related headers when `settings.enable_security_headers` is true.
  - Skips adding headers for WebSocket upgrade requests (`/ws/...` or `Upgrade: websocket`).
  - Uses `is_embeddable()` / `embed_csp()` to selectively allow framing for certain paths; otherwise sets `X-Frame-Options: DENY`.
  - Sets/overrides headers including (depending on environment/config):
    - `X-Content-Type-Options`, `Referrer-Policy`, `Permissions-Policy`
    - `Strict-Transport-Security` (production only)
    - `Content-Security-Policy` (from settings, or a strict default in production)

## Configuration/Dependencies

### Key internal dependencies
- Configuration:
  - `settings`
  - `validate_settings_on_startup()`
- Startup/runtime services:
  - `configure_logging()`
  - `init_db()` (database init/migrations; raises `ConnectionError` on failure)
  - `register_service_exception_handlers(app)`
  - `init_websocket(app)` (wraps the app; must be applied last)
  - `start_chat_ingestion_consumer(app)` (best-effort)
  - Configuration seeding: `apply_configuration_seeds(...)`
  - Several background startup tasks (agent registry prefetch, modules catalog prefetch, model catalog sync, identity graph sync, drive backfill)

### Middleware configured (in `_configure_middleware`)
- `SettingsCacheMiddleware`
- `CORSMiddleware`
  - `allow_origins` from `app.state.abi_cors_origins` or `[settings.frontend_url]`
  - In `local` or `development`: additionally sets `allow_origin_regex` to accept any localhost origin.
- `SecurityHeadersMiddleware`
- `HttpActivityLogMiddleware` (no-op if `app.state.activity_log_service` is missing)
- `RequestIdentityMiddleware`
- `RemoteAppPreflight` (and access-log redaction for remote app grants)
- `TracingMiddleware` (no-op unless telemetry enabled by engine config)

### Static assets
- `/logos/{path:path}` served via a handler that overlays:
  - project: `Path.cwd() / "storage/logos"`
  - defaults: `<package>/public/logos`
- `/avatars`, `/organizations` mounted if their directories exist under `<package>/public/...`
- `/uploads` mounted from `<package>/uploads` (created if missing)

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
asgi_app = create_app(base)  # returns a wrapped ASGI app
```

## Caveats
- `create_app(...)` returns the WebSocket-wrapped ASGI callable from `init_websocket(app)`, not necessarily the original `FastAPI` instance.
- When patching an existing app (passing `app` to `create_app`), startup/shutdown handlers are attached via `add_event_handler`; when `create_app()` constructs the app itself, it uses the `lifespan` context manager instead.
- Startup fails (and prevents serving) if `init_db()` raises `ConnectionError`.
- OpenAPI docs (`/docs`, `/redoc`) are disabled unless `settings.debug` is true or `settings.environment == "development"`.
- Security headers middleware intentionally skips WebSocket upgrade requests.
