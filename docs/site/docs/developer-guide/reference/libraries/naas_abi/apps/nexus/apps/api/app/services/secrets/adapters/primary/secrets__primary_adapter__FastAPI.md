# SecretsFastAPIPrimaryAdapter (Secrets FastAPI primary adapter)

## What it is
- A FastAPI “primary adapter” exposing HTTP endpoints for managing workspace secrets.
- Provides a module-level `router` (`fastapi.APIRouter`) with endpoints to list, create, update, delete, and bulk-import secrets.
- Integrates authentication and workspace access control via dependencies.

## Public API

### Router
- `router: APIRouter`
  - Configured with `dependencies=[Depends(get_current_user_required)]` (all endpoints require an authenticated user dependency, except behavior is still applied per-route).

### Class
- `class SecretsFastAPIPrimaryAdapter`
  - `__init__(self) -> None`: assigns the module `router` to `self.router`.

### Dependency providers / helpers
- `get_secrets_service(db: AsyncSession = Depends(get_db)) -> SecretsService`
  - Builds a `SecretsService` using `SecretsSecondaryAdapterPostgres(db=db)` and `require_workspace_access` as the workspace access checker.
- `request_context(current_user: User) -> RequestContext`
  - Creates a `RequestContext` with `TokenData(user_id=..., scopes={"*"}, is_authenticated=True)`.

### Pydantic models (request/response)
- `SecretCreate`
  - Fields: `workspace_id`, `key`, `value`, `description`, `category`.
- `SecretUpdate`
  - Fields: `value` (optional), `description` (optional).
- `SecretResponse`
  - Fields: `id`, `workspace_id`, `key`, `masked_value`, `description`, `category`, `created_at`, `updated_at`.
- `SecretBulkImport`
  - Fields: `workspace_id`, `env_content`.

### Endpoints (mounted on `router`)
- `GET /{workspace_id}` → `list_secrets(...) -> list[SecretResponse]`
  - Requires `require_workspace_access(current_user.id, workspace_id)`.
  - Returns secrets for a workspace.
- `POST /` → `create_secret(...) -> SecretResponse`
  - Requires workspace role `admin` or `owner`.
  - Creates a secret; maps `SecretAlreadyExistsError` to HTTP 409.
- `PUT /{secret_id}` → `update_secret(...) -> SecretResponse`
  - Looks up secret by id via `service.adapter.get_by_id`.
  - Requires workspace role `admin` or `owner`.
  - Maps missing secret to HTTP 404.
- `DELETE /{secret_id}` → `delete_secret(...) -> dict`
  - Looks up secret by id via `service.adapter.get_by_id`.
  - Requires workspace role `admin` or `owner`.
  - Returns `{"status": "deleted"}` on success; 404 if not found.
- `POST /import` → `bulk_import_secrets(...) -> dict`
  - Requires workspace role `admin` or `owner`.
  - Bulk-imports from dotenv-like content; returns `{"imported": ..., "updated": ...}`.
- `GET /test-public` → `test_public_endpoint() -> dict`
  - Returns `{"message": "Public secrets endpoint working!"}`.
  - Note: the router itself is configured with `get_current_user_required` dependency, so this may still require authentication depending on FastAPI dependency behavior in your app wiring.

## Configuration/Dependencies
- FastAPI:
  - `APIRouter`, `Depends`, `HTTPException`
- Auth/access control:
  - `get_current_user_required` (router-wide dependency and per-route injection)
  - `require_workspace_access(user_id, workspace_id)` returning a role string (checked against `"admin"`/`"owner"` for write operations)
- Database:
  - `get_db` provides `sqlalchemy.ext.asyncio.AsyncSession`
  - `SecretsSecondaryAdapterPostgres(db=...)` as the persistence adapter
- Service layer:
  - `SecretsService` with methods `list_secrets`, `create_secret`, `update_secret`, `delete_secret`, `bulk_import`
- Time:
  - Uses `datetime.now(UTC).replace(tzinfo=None)` when calling service methods that require `now`.

## Usage

### Mounting the router in a FastAPI app
```python
from fastapi import FastAPI
from naas_abi.apps.nexus.apps.api.app.services.secrets.adapters.primary.secrets__primary_adapter__FastAPI import router

app = FastAPI()
app.include_router(router, prefix="/secrets", tags=["secrets"])
```

## Caveats
- Write operations (`POST /`, `PUT /{secret_id}`, `DELETE /{secret_id}`, `POST /import`) are restricted to workspace roles `"admin"` and `"owner"`; otherwise HTTP 403.
- `GET /test-public` is named “public” but the router applies `Depends(get_current_user_required)` globally; whether it is truly public depends on how that dependency behaves in your environment.
- Timestamps passed to the service are timezone-naive (`tzinfo=None`) even though derived from `UTC`.
