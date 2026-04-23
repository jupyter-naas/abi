# ABI Server Configuration API (`abi.py`)

## What it is
FastAPI endpoints and schemas to manage external ABI server configurations per workspace (CRUD). Each ABI server record includes name, endpoint, enabled flag, timestamps, and an optionally stored (encrypted) API key.

## Public API

### FastAPI router
- `router: fastapi.APIRouter`
  - Mount this router into a FastAPI app to expose the endpoints below.

### Pydantic schemas
- `class ABIServer(BaseModel)`
  - Response model for an ABI server record.
  - Fields: `id`, `workspace_id`, `name`, `endpoint`, `enabled`, `created_at`, `updated_at`.
- `class ABIServerCreate(BaseModel)`
  - Request model for creating a server.
  - Fields:
    - `name` (required, 1–255 chars)
    - `endpoint` (required, min length 1)
    - `api_key` (optional)
- `class ABIServerUpdate(BaseModel)`
  - Request model for updating a server.
  - Fields (all optional):
    - `name` (1–255 chars)
    - `endpoint` (min length 1)
    - `api_key`
    - `enabled`

### Helper
- `_to_abi_server(row: ABIServerModel) -> ABIServer`
  - Converts a DB model row (`ABIServerModel`) into an `ABIServer` response schema.

### Endpoints
- `GET /workspaces/{workspace_id}/abi-servers` → `list[ABIServer]`
  - Lists all ABI servers for a workspace.
- `POST /workspaces/{workspace_id}/abi-servers` → `ABIServer`
  - Creates a new ABI server for a workspace.
  - Rejects duplicates: if another server in the same workspace already has the same `endpoint`, returns `400`.
- `GET /workspaces/{workspace_id}/abi-servers/{server_id}` → `ABIServer`
  - Retrieves one ABI server by `server_id` within the workspace.
  - If not found, returns `404`.
- `PUT /workspaces/{workspace_id}/abi-servers/{server_id}` → `ABIServer`
  - Updates an ABI server (patch-like behavior; only provided fields are changed).
  - If not found, returns `404`.
- `DELETE /workspaces/{workspace_id}/abi-servers/{server_id}` → `{"status": "deleted"}`
  - Deletes an ABI server.
  - If not found, returns `404`.

## Configuration/Dependencies
- Authentication/authorization:
  - `get_current_user_required` (FastAPI dependency) provides `current_user: User`.
  - `require_workspace_access(current_user.id, workspace_id)` is enforced on every endpoint.
- Database:
  - `db: AsyncSession = Depends(get_db)` uses SQLAlchemy async session.
  - Uses `ABIServerModel` and `select(...)` queries.
- Time handling:
  - Uses `datetime.now(UTC).replace(tzinfo=None)` for `created_at`/`updated_at` (naive datetime).
- API key storage:
  - `deprecated_encrypt(...)` is applied when `api_key` is provided; stored value is not returned by the API.
- ID format:
  - Created IDs are generated as `abi-` + 12 hex chars from a UUID4 (`abi-xxxxxxxxxxxx`).

## Usage

### Mounting the router
```python
from fastapi import FastAPI
from naas_abi.apps.nexus.apps.api.app.api.endpoints.abi import router as abi_router

app = FastAPI()
app.include_router(abi_router)
```

## Caveats
- `api_key` is write-only in this module: it can be set/updated but is never returned in responses.
- `created_at` and `updated_at` are stored/returned as naive `datetime` values (timezone removed via `.replace(tzinfo=None)`).
- On create, `endpoint` must be unique per workspace; otherwise the API returns HTTP 400.
