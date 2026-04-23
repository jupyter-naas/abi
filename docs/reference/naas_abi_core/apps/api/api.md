# `naas_abi_core.apps.api.api`

## What it is
- A FastAPI application entrypoint for the Naas ABI Core API.
- Lazily initializes the runtime `Engine`, mounts static assets, configures CORS, exposes custom docs endpoints, and dynamically registers routes from engine modules/agents.
- Provides a simple bearer-token check that accepts tokens from either the `Authorization: Bearer ...` header or a `?token=...` query parameter.

## Public API
### Application objects
- `app: fastapi.FastAPI`
  - FastAPI instance with `docs_url=None` and `redoc_url=None` (custom endpoints provided instead).

- `get_app() -> fastapi.FastAPI`
  - Ensures runtime routes are loaded (once) and returns the configured `app`.
  - Intended for use by Uvicorn factory mode when reload is enabled.

### Server runner
- `api()`
  - Runs Uvicorn on `0.0.0.0:9879`.
  - Uses reload settings from runtime API configuration.
  - In reload mode, runs via factory target `"naas_abi_core.apps.api.api:get_app"`.

### Health/initialization test
- `test_init()`
  - Logs and prints a sentinel string (`API_INIT_TEST_PASSED`) to validate import/init.

### Authentication helpers
- `class OAuth2QueryBearer(fastapi.security.oauth2.OAuth2)`
  - OAuth2 “password flow” security scheme that extracts bearer tokens from:
    - `Authorization` header (preferred), or
    - `token` query parameter.

- `is_token_valid(token: str = Depends(oauth2_scheme))`
  - Dependency that validates the extracted token equals `os.environ["ABI_API_KEY"]` (exact match).
  - Raises `401 Unauthorized` on mismatch.

### Routes (defined in this module)
- `POST /token` (excluded from OpenAPI schema)
  - Accepts `OAuth2PasswordRequestForm`.
  - Validates `password == "abi"` (username is not checked).
  - Returns `{"access_token": "abi", "token_type": "bearer"}`.
- `GET /docs` (excluded from OpenAPI schema)
  - Swagger UI with custom favicon.
- `GET /redoc` (excluded from OpenAPI schema)
  - ReDoc with custom favicon.
- `GET /` (excluded from OpenAPI schema)
  - Returns HTML landing page from `API_LANDING_HTML` with title/logo substitutions.

### Dynamic routing (runtime-loaded)
- `_load_runtime_routes()` (internal)
  - Builds agent APIs under `/agents` by calling each runtime agent’s `as_api(agents_router)`.
  - Includes routers:
    - `/agents` (token-protected)
    - `/pipelines` (token-protected; router created here but endpoints are added elsewhere)
    - `/workflows` (token-protected; router created here but endpoints are added elsewhere)
  - Invokes each module’s `module.api(app)` to attach module-defined routes.

## Configuration/Dependencies
### Runtime configuration
Loaded via `EngineConfiguration.load_configuration().api` (fallbacks to defaults on error):
- `title`, `description`
- `logo_path`, `favicon_path` (used for docs and landing page; served from `/static`)
- `cors_origins` (passed to `CORSMiddleware`)
- `reload` (controls Uvicorn reload behavior)

### Environment variables
- `ABI_API_KEY`
  - Required for authenticated routes (routers use `Depends(is_token_valid)`).

### Static assets
- Mounts `naas_abi_core/assets` at `/static`.

### Versioning
- OpenAPI `version` is taken from:
  1. `git describe --tags`, else
  2. local `VERSION` file, else
  3. `"v0.0.1"`.

## Usage
### Run the API server
```python
from naas_abi_core.apps.api.api import api

api()
```

### Run with Uvicorn (factory when reload enabled)
```bash
uvicorn naas_abi_core.apps.api.api:get_app --factory --host 0.0.0.0 --port 9879
```

### Call an authenticated endpoint (token via header or query)
```python
import os
import requests

base = "http://localhost:9879"
token = os.environ["ABI_API_KEY"]

# Header-based
r = requests.get(f"{base}/agents", headers={"Authorization": f"Bearer {token}"})

# Or query-based
r2 = requests.get(f"{base}/agents", params={"token": token})
```

## Caveats
- Auth is a simple equality check against `ABI_API_KEY`; no JWT/OAuth token issuance is enforced for protected routes.
- `POST /token` returns a fixed token (`"abi"`) when password is `"abi"`, but protected endpoints validate against `ABI_API_KEY`, not the `/token` output.
- Dynamic routes are loaded lazily on first `get_app()` call; direct use of `app` without calling `get_app()` may miss runtime routes.
