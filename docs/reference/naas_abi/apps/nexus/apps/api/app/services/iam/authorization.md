# authorization

## What it is
Utility functions for IAM- and workspace-related authorization in the Nexus API service layer. Provides helpers to:
- Resolve `IAMService` / `WorkspaceService` from an optional explicit instance or the global service registry.
- Enforce required IAM scopes.
- Enforce per-workspace access for a user.

## Public API

- `resolve_iam_service(explicit_iam_service: IAMService | None = None) -> IAMService | None`
  - Returns the provided `explicit_iam_service`, otherwise attempts to fetch `ServiceRegistry.instance().iam` if a Postgres session is available.
  - Returns `None` if no current session exists or on any exception.

- `resolve_workspace_service(explicit_workspace_service: WorkspaceService | None = None) -> WorkspaceService | None`
  - Returns the provided `explicit_workspace_service`, otherwise attempts to fetch `ServiceRegistry.instance().workspaces` if a Postgres session is available.
  - Returns `None` if no current session exists or on any exception.

- `ensure_scope(context: RequestContext, required_scope: str, denied_message: str, iam_service: IAMService | None = None) -> None`
  - Ensures `context.token_data` has `required_scope` using the resolved `IAMService`.
  - If IAM service cannot be resolved, this function is a no-op.
  - Raises `PermissionError(denied_message)` when `IAMService.ensure(...)` raises `IAMPermissionError`.

- `ensure_workspace_access(...) -> str | None` (async)
  - Signature:
    - `context: RequestContext`
    - `workspace_id: str`
    - `denied_message: str = "Workspace access denied"`
    - `required_scope: str = "workspace.read"`
    - `iam_service: IAMService | None = None`
    - `workspace_service: WorkspaceService | None = None`
  - First enforces the IAM scope via `ensure_scope(...)`.
  - Then calls `WorkspaceService.require_workspace_access(user_id=context.actor_user_id, workspace_id=workspace_id)`.
  - Returns the result of `require_workspace_access(...)`, or `None` if workspace service cannot be resolved.
  - Wraps workspace `PermissionError` as `PermissionError(denied_message)`.

## Configuration/Dependencies
- Depends on:
  - `RequestContext` (must provide at least `token_data` and `actor_user_id`).
  - `IAMService` with method `ensure(token_data, required_scope)`.
  - `WorkspaceService` with async method `require_workspace_access(user_id, workspace_id)`.
- Optional runtime resolution uses:
  - `PostgresSessionRegistry.instance().current_session()` (must be non-`None` to resolve services).
  - `ServiceRegistry.instance().iam` and `ServiceRegistry.instance().workspaces`.
- Resolution is defensive: any exception during import/lookup results in `None`.

## Usage
Minimal example using explicit service instances (no registry/session required):

```python
import asyncio
from dataclasses import dataclass

from naas_abi.apps.nexus.apps.api.app.services.iam.authorization import (
    ensure_scope,
    ensure_workspace_access,
)

@dataclass
class Ctx:
    token_data: dict
    actor_user_id: str

class FakeIAM:
    def ensure(self, token_data, required_scope):
        if required_scope not in token_data.get("scopes", []):
            # In real usage, IAMService raises IAMPermissionError.
            raise Exception("denied")

class FakeWorkspaces:
    async def require_workspace_access(self, user_id, workspace_id):
        if workspace_id != "ws_ok":
            raise PermissionError("no access")
        return workspace_id

async def main():
    ctx = Ctx(token_data={"scopes": ["workspace.read"]}, actor_user_id="user_1")

    ensure_scope(ctx, required_scope="workspace.read", denied_message="Denied", iam_service=FakeIAM())

    ws_id = await ensure_workspace_access(
        context=ctx,
        workspace_id="ws_ok",
        iam_service=FakeIAM(),
        workspace_service=FakeWorkspaces(),
    )
    print(ws_id)

asyncio.run(main())
```

## Caveats
- If no explicit services are passed and no current Postgres session exists (or service resolution fails), authorization checks become a no-op:
  - `ensure_scope(...)` returns without enforcing.
  - `ensure_workspace_access(...)` returns `None` without checking workspace access.
- `ensure_scope(...)` only converts `IAMPermissionError` into `PermissionError`; other exceptions from `IAMService.ensure(...)` are not handled here.
