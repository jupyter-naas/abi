# ABI Server Configuration API (`abi.py`)

## What it is
FastAPI endpoints and Pydantic schemas for managing external ABI server configurations per workspace (list/create/get/update/delete).

## Public API

### FastAPI router
- `router: fastapi.APIRouter`
  - Mounts the endpoints listed below.

### Pydantic schemas
- `class ABIServer(BaseModel)`
  - Response model for an ABI server record.
  - Fields: `id`, `workspace_id`, `name`, `endpoint`, `enabled`, `created_at`, `updated_at`.
- `class ABIServerCreate(BaseModel)`
  - Request model for creating an ABI server.
  - Fields:
    - `name` (required, 1–255 chars)
    - `endpoint` (required, min length 1)
    - `api_key` (optional)
- `class ABIServerUpdate(BaseModel)`
  - Request model for updating an ABI server.
  - Fields (all optional): `name`, `endpoint`, `api_key`, `enabled`.

### Helper
- `_to_abi_server(row: ABIServerModel) -> ABIServer`
  - Converts a SQLAlchemy `ABIServerModel` row to an `ABIServer` response model.

### Endpoints
- `GET /workspaces/{workspace_id}/abi-servers` → `list_abi_servers(...) -> list[ABIServer]`
  - Lists all ABI servers for a workspace.
- `POST /workspaces/{workspace_id}/abi-servers` → `create_abi_server(...) -> ABIServer`
  - Creates a new ABI server for a workspace.
  - Rejects duplicates by `endpoint` within the same workspace (`400`).
  - Generates an id like `abi-<12 hex chars>`.
  - Encrypts `api_key` before storing (if provided).
  - Sets `enabled=True`.
- `GET /workspaces/{workspace_id}/abi-servers/{server_id}` → `get_abi_server(...) -> ABIServer`
  - Fetches a single ABI server by id within a workspace (`404` if not found).
- `PUT /workspaces/{workspace_id}/abi-servers/{server_id}` → `update_abi_server(...) -> ABIServer`
  - Updates fields provided in `ABIServerUpdate` (`404` if not found).
  - If `api_key` is provided:
    - Encrypts non-empty value
    - Stores `None` if empty string/falsy.
- `DELETE /workspaces/{workspace_id}/abi-servers/{server_id}` → `delete_abi_server(...) -> dict[str, str]`
  - Deletes a server (`404` if not found).
  - Returns `{"status": "deleted"}`.

## Configuration/Dependencies
- Authentication/authorization:
  - `get_current_user_required` (FastAPI dependency) to require an authenticated user.
  - `require_workspace_access(user_id, workspace_id)` is called in every endpoint to enforce workspace access.
- Database:
  - `get_db` provides an `sqlalchemy.ext.asyncio.AsyncSession`.
  - Uses `ABIServerModel` (SQLAlchemy model) and `select(...)` queries.
- Secrets:
  - `_encrypt(...)` is used to encrypt API keys before persistence.
- Time:
  - Uses `datetime.now(UTC).replace(tzinfo=None)` for `created_at`/`updated_at`.

## Usage

### Mount the router in a FastAPI app
```python
from fastapi import FastAPI
from naas_abi.apps.nexus.apps.api.app.api.endpoints.abi import router as abi_router

app = FastAPI()
app.include_router(abi_router)
```

## Caveats
- API keys are never returned by the API (not present in `ABIServer` response model).
- `created_at`/`updated_at` timestamps are stored as *naive* datetimes (`tzinfo` removed).
- Duplicate prevention on create only checks `(workspace_id, endpoint)`; update does not prevent changing an endpoint to collide with another record.
