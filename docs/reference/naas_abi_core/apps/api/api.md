# `naas_abi_core.apps.api.api`

## What it is
- FastAPI application entrypoint for the Naas ABI Core API.
- Lazily loads the runtime `Engine`, then dynamically mounts:
  - agent APIs under `/agents`
  - workflow/pipeline/tool process APIs when present
  - module-defined routes and module public assets
- Serves custom Swagger/ReDoc endpoints and a simple HTML landing page.
- Enforces an API key via bearer auth, accepting the token from either:
  - `Authorization: Bearer <token>` header, or
  - `?token=<token>` query parameter.

## Public API

### Application objects
- `app: fastapi.FastAPI`
  - Base FastAPI instance (`docs_url=None`, `redoc_url=None`) with custom docs routes.

- `get_app() -> fastapi.FastAPI`
  - Loads runtime routes once (engine/module/agent mounting) and returns the configured `app`.
  - In case of startup failure, attempts to shut down and forget the engine.

### Server runner
- `api() -> None`
  - Runs Uvicorn using runtime configuration.
  - Supports reload mode (uses factory string target `naas_abi_core.apps.api.api:get_app`).

### Auth / security
- `class QueryOrHeaderBearer(HTTPBearer)`
  - Security scheme extracting a bearer token from header or `token` query parameter.

- `oauth2_scheme`
  - Alias to `api_key_scheme` kept for backward compatibility with modules importing `oauth2_scheme`.

- `is_token_valid(token: str = Depends(api_key_scheme))`
  - Dependency that validates the provided token via `naas_abi_core.apps.api.abi_api_key_auth.is_abi_api_token_valid`.
  - Raises `401` if invalid.

### Routers (mounted dynamically)
- `agents_router: APIRouter` (prefix `/agents`, protected)
- `pipelines_router: APIRouter` (prefix `/pipelines`, protected; included only if it has routes)
- `workflows_router: APIRouter` (prefix `/workflows`, protected; included only if it has routes)
- `tools_router: APIRouter` (prefix `/tools`, protected; included only if it has routes)

### Endpoints defined in this module
- `GET /branding/{name}` (no schema)
  - Serves configured logo/favicon files when they are local files.
- `GET /docs` (no schema)
  - Swagger UI using configured favicon.
- `GET /redoc` (no schema)
  - ReDoc using configured favicon.
- `GET /` (no schema)
  - HTML landing page rendered from `API_LANDING_HTML`.

### Utilities
- `resolve_branding_asset(configured: str) -> tuple[str, str | None]`
  - Resolves configured branding paths/URLs into a browser URL and optional local file path.
- `trusted_proxy_ips() -> str`
  - Returns `FORWARDED_ALLOW_IPS` or a default allowlist used by Uvicorn.
- `get_git_tag() -> str`
  - Determines OpenAPI version from `git describe --tags`, else `VERSION`, else `v0.0.1`.
- `custom_openapi()`
  - Generates OpenAPI schema and injects `info.x-logo`.

### Initialization test
- `test_init() -> None`
  - Logs and prints `API_INIT_TEST_PASSED`.

## Configuration/Dependencies

### Runtime configuration
Loaded via `EngineConfiguration.load_configuration()`:
- `api_runtime_configuration.title`, `description`
- `api_runtime_configuration.logo_path`, `favicon_path`
- `api_runtime_configuration.cors_origins` (mutated to include `ABI_CORS_EXTRA_ORIGINS`)
- `api_runtime_configuration.host`, `port`
- `api_runtime_configuration.reload`

### Environment variables
- `ABI_HOST`, `ABI_PORT`: override configured host/port.
- `ABI_CORS_EXTRA_ORIGINS`: comma-separated extra CORS origins appended at runtime.
- `FORWARDED_ALLOW_IPS`: forwarded proxy allowlist for Uvicorn; defaults to loopback + private networks.
- `TEST_INIT=true` or `--test-init`: run `test_init()` instead of starting the server.

### Static assets
- Mounts `naas_abi_core/assets` at `/static`.
- If `logo_path`/`favicon_path` are local files, they are served via `/branding/<basename>`.

### Engine / module integration
Runtime route loading:
- Instantiates and loads `Engine()` on first use.
- For each module:
  - Instantiates agents (`agent.New()`) and mounts agent APIs via `runtime_agent.as_api(agents_router)`.
  - Mounts module process APIs via `naas_abi_core.utils.process_api.mount_module_processes(...)`.
  - Optionally mounts module public assets from `<module_root>/assets/public` under:
    - `/modules/<module.__class__.__module__.replace('.', '/')>/assets/public`
  - Calls `module.api(app)` to add module routes.
- Adds `AppHtmlAbiKeyMiddleware` (from `naas_abi_core.apps.api.abi_api_key_auth`) after routes are loaded.
- Attempts background warmup via `IntentMapper.warm_all_in_background()` (best-effort).

## Usage

### Run the API server (in-process)
```python
from naas_abi_core.apps.api.api import api

api()
```

### Run with Uvicorn (recommended for reload)
```bash
uvicorn naas_abi_core.apps.api.api:get_app --factory
```

### Call a protected endpoint (header or query token)
```python
import requests

base = "http://localhost:9879"
token = "your-api-key"

# Header token
requests.get(f"{base}/agents", headers={"Authorization": f"Bearer {token}"}).raise_for_status()

# Query token
requests.get(f"{base}/agents", params={"token": token}).raise_for_status()
```

## Caveats
- Runtime routes are loaded lazily; importing `app` directly does not load engine/module routes until `get_app()` is called.
- `/pipelines`, `/workflows`, and `/tools` routers are only included if routes were registered (they may not appear at all).
- Engine shutdown is handled in the FastAPI lifespan; if startup fails after engine load, the code attempts to shut the engine down early to release resources.
