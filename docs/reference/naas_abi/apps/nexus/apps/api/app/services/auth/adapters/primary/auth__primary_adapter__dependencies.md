# auth__primary_adapter__dependencies

## What it is
FastAPI dependency helpers for the Auth primary adapter:
- Defines an OAuth2 bearer token scheme.
- Wires an `AuthService` backed by a Postgres secondary adapter.
- Provides dependencies to resolve the current user (optional/required).
- Provides async helpers to check workspace role/access using a scoped Postgres session registry.

## Public API
- `oauth2_scheme: OAuth2PasswordBearer`
  - Extracts a bearer token from the request (`tokenUrl="/api/auth/token"`, `auto_error=False`).

- `to_user_schema(user: AuthUserRecord) -> User`
  - Converts an internal auth user record to the API `User` schema.

- `get_auth_service(db: AsyncSession = Depends(get_db)) -> AuthService`
  - FastAPI dependency that instantiates `AuthService(adapter=AuthSecondaryAdapterPostgres(db=db))`.

- `get_current_user(token: str | None = Depends(oauth2_scheme), auth_service: AuthService = Depends(get_auth_service)) -> User | None`
  - Resolves the current user from an access token via `auth_service.get_user_from_access_token(token)`.
  - Returns `None` if unauthenticated/invalid.

- `get_current_user_required(current_user: User | None = Depends(get_current_user)) -> User`
  - Ensures a user is present; otherwise raises `HTTPException(401, "Not authenticated")`.

- `get_workspace_role(user_id: str, workspace_id: str) -> str | None`
  - Uses `ServiceRegistry.instance().workspaces.get_workspace_role(...)` within a bound `PostgresSessionRegistry` session.

- `require_workspace_access(user_id: str, workspace_id: str) -> str`
  - Uses `ServiceRegistry.instance().workspaces.require_workspace_access(...)`.
  - Translates `WorkspacePermissionError` into `HTTPException(403, "You do not have access to this workspace")`.

- Re-exported: `decode_token`
  - Imported from `naas_abi...services.auth.service` and included in `__all__`.

## Configuration/Dependencies
- Database/session:
  - `AsyncSessionLocal` is used directly for workspace access checks.
  - `get_db` provides an `AsyncSession` for `get_auth_service`.

- Registries/services:
  - `ServiceRegistry.instance()` must be configured and provide `.workspaces`.
  - `PostgresSessionRegistry.instance()` is used to bind/unbind a generated session id and set/reset current session.

- Security:
  - Bearer token extraction uses FastAPI’s `OAuth2PasswordBearer` with `auto_error=False` (token may be absent).

## Usage
```python
from fastapi import FastAPI, Depends
from naas_abi.apps.nexus.apps.api.app.services.auth.adapters.primary.auth__primary_adapter__dependencies import (
    get_current_user_required,
    require_workspace_access,
    User,
)

app = FastAPI()

@app.get("/me")
async def me(user: User = Depends(get_current_user_required)):
    return user

@app.get("/workspaces/{workspace_id}")
async def workspace_info(
    workspace_id: str,
    user: User = Depends(get_current_user_required),
):
    role = await require_workspace_access(user_id=user.id, workspace_id=workspace_id)
    return {"workspace_id": workspace_id, "role": role}
```

## Caveats
- `get_current_user_required` always returns `401` when no user is resolved; it does not attempt redirects or alternative auth flows.
- `require_workspace_access` maps only `WorkspacePermissionError` to `403`; other exceptions are not handled here.
- Workspace helpers create their own `AsyncSessionLocal()` session and manage `PostgresSessionRegistry` binding/unbinding internally.
