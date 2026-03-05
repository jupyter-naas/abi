# `naas_abi_core.apps.api.api`

## What it is
- A FastAPI application factory and runner for the `naas_abi_core` API.
- Loads runtime routes from an `Engine` (agents + module APIs) on first access.
- Provides custom OpenAPI metadata and custom docs endpoints.
- Secures most routes with a bearer token that can be provided via header or query string.

## Public API

### Module globals
- `app: fastapi.FastAPI`
  - The FastAPI app instance (docs are disabled on the default URLs).
- `engine: LazyEngine`
  - Lazily instantiates and loads `naas_abi_core.engine.Engine.Engine`.
- `api_runtime_configuration: ApiConfiguration`
  - Loaded from `EngineConfiguration.load_configuration().api` (falls back to defaults on error).

### Classes
- `LazyEngine`
  - `get() -> Engine`: Create/load the engine on first call and return it.
  - `__getattr__(name: str)`: Proxy attribute access to the underlying engine.

- `OAuth2QueryBearer(OAuth2)`
  - OAuth2 password flow security scheme that accepts bearer tokens from:
    - `Authorization: Bearer <token>` header (preferred), or
    - `?token=<token>` query parameter.

### Functions
- `get_app() -> FastAPI`
  - Ensures runtime routes are loaded once, then returns the `app`.

- `api() -> None`
  - Runs the API using `uvicorn` on `0.0.0.0:9879`.
  - When `api_runtime_configuration.reload` is enabled, runs uvicorn in factory mode using `get_app`.

- `test_init() -> None`
  - Logs and prints a success marker (`API_INIT_TEST_PASSED`).

### FastAPI endpoints (defined in this module)
- `POST /token` (excluded from OpenAPI schema)
  - Accepts `OAuth2PasswordRequestForm`.
  - Succeeds only if `password == "abi"`, returning `{"access_token": "abi", "token_type": "bearer"}`.
- `GET /docs` (excluded)
  - Swagger UI using `/openapi.json` and custom favicon.
- `GET /redoc` (excluded)
  - ReDoc using `/openapi.json` and custom favicon.
- `GET /` (excluded)
  - Returns a landing HTML page using `API_LANDING_HTML` template.

### Routers (included at runtime)
- `/agents` (tag: `Agents`) — protected by token validation.
- `/pipelines` (tag: `Pipelines`) — protected by token validation.
- `/workflows` (tag: `Workflows`) — protected by token validation.
- Additional module routes: each engine module is allowed to register routes via `module.api(app)`.

## Configuration/Dependencies
- **Runtime API configuration**
  - Loaded via `EngineConfiguration.load_configuration().api`
  - Used fields include:
    - `title`, `description`
    - `logo_path`, `favicon_path`
    - `cors_origins`
    - `reload` (controls uvicorn reload/factory mode)

- **Authentication**
  - Token validator `is_token_valid` compares the incoming token with environment variable:
    - `ABI_API_KEY`
  - Token can be provided via:
    - `Authorization: Bearer <token>`
    - `?token=<token>`

- **Static assets**
  - Mounts `GET /static/*` from `naas_abi_core/assets`.
  - OpenAPI `x-logo` points to `/static/<logo file name>`.

- **OpenAPI version**
  - Uses `git describe --tags` when available.
  - Fallbacks:
    - reads local `VERSION` file if present
    - otherwise defaults to `v0.0.1`

## Usage

### Run with uvicorn via the module entrypoint
```python
from naas_abi_core.apps.api.api import api

api()  # serves on 0.0.0.0:9879
```

### Embed the app in another server (factory)
```python
from naas_abi_core.apps.api.api import get_app

app = get_app()
```

### Call a protected endpoint with a token
```python
import os
import requests

os.environ["ABI_API_KEY"] = "my-secret"
r = requests.get("http://localhost:9879/agents", headers={"Authorization": "Bearer my-secret"})
print(r.status_code)
```

## Caveats
- `/token` issues a fixed token (`"abi"`) but protected routes validate against `ABI_API_KEY`; these are not automatically aligned.
- Runtime routes are only loaded the first time `get_app()` (or `_load_runtime_routes()`) is executed; importing `app` alone does not load engine/module routes.
- If engine modules/agents depend on external configuration (e.g., API keys), missing agents may be skipped (`"Skipping agent (missing API key)"`).
