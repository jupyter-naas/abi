# XCountAppMiddleware (x/apps/x/routes.py)

## What it is
- FastAPI middleware that serves the **X Recent Tweets** dashboard (static Next.js export) and its **published JSON dataset** directly from object storage.
- Handles deep links by serving per-route `index.html` pages and optional `index.txt` route payloads.
- Runs as middleware to intercept `/app-html/x/apps/x/...` **before** a higher-priority static catch-all route.

## Public API
- `class XCountAppMiddleware(BaseHTTPMiddleware)`
  - Intercepts `GET` requests under `/app-html/x/apps/x/` and serves:
    - App root: `index.html`
    - Page snapshots: `.../<route>/index.html`
    - Client router payloads: `.../index.txt` (if present)
    - Dataset JSON: `globals/...json`, `count_recent_tweets/...json`, `search_recents_tweets/...json`, `search_users/...json` (plus legacy `data/*.json`)
    - Static assets: `_next/...`, and common web assets (js/css/fonts/images/etc.)
  - Redirects unslashed page paths (e.g., `/users/search`) to slashed form (`/users/search/`) with status `308`.

- `def register_x_count_app_routes(app: FastAPI, object_storage_service: ObjectStorageService) -> None`
  - Mounts `XCountAppMiddleware` onto the provided FastAPI app.
  - Required dependency: `ObjectStorageService` (used to fetch published objects).

## Configuration/Dependencies
- **FastAPI / Starlette**
  - Uses `BaseHTTPMiddleware`, `Response`, `RedirectResponse`, `HTTPException`, `Request`.
- **Object storage**
  - Requires `naas_abi_core.services.object_storage.ObjectStorageService.ObjectStorageService`.
  - Handles missing objects via `naas_abi_core.services.object_storage.ObjectStoragePort.Exceptions.ObjectNotFound`.
- **Object key prefix**
  - Reads objects under `DEFAULT_APP_PREFIX` (imported from `naas_abi_marketplace.applications.x.apps.x.api.common`).
- **Served URL prefix**
  - Middleware responds only for paths starting with: `/app-html/x/apps/x/`

## Usage
```python
from fastapi import FastAPI
from naas_abi_core.services.object_storage.ObjectStorageService import ObjectStorageService
from naas_abi_marketplace.applications.x.apps.x.routes import register_x_count_app_routes

app = FastAPI()

object_storage_service = ObjectStorageService(...)  # provide your implementation/config

register_x_count_app_routes(app, object_storage_service)
```

## Caveats
- Only intercepts **GET** requests; other methods pass through to downstream routing.
- If `index.html` is missing (nothing published yet), the middleware defers to the downstream app (e.g., a static catch-all).
- Missing `index.txt` payloads are tolerated (older publishes); request is passed through rather than raising within middleware.
- Adds a `Content-Security-Policy` `frame-ancestors` header derived from request `Origin` / `Referer` (falls back to `'self'`).
