# ServiceRegistry

## What it is
A lightweight, global service container for FastAPI that:
- Stores references to core application services (IAM, chat, search, agents, workspaces, organizations).
- Provides a FastAPI dependency (`get_service_registry`) that binds an `AsyncSession` to a per-request session in `PostgresSessionRegistry`.

## Public API

### `RegistryServices` (dataclass)
Immutable container of service instances:
- `iam: IAMService`
- `chat: ChatService`
- `search: SearchService`
- `agents: AgentService`
- `workspaces: WorkspaceService`
- `organizations: OrganizationService`

### `ServiceRegistry`
Singleton registry for accessing services.

- `ServiceRegistry.configure(services: RegistryServices) -> ServiceRegistry`
  - Initializes/configures the singleton instance.

- `ServiceRegistry.instance() -> ServiceRegistry`
  - Returns the configured singleton.
  - Raises `RuntimeError` if not configured.

- Service accessors (properties):
  - `iam -> IAMService`
  - `chat -> ChatService`
  - `agents -> AgentService`
  - `search -> SearchService`
  - `workspaces -> WorkspaceService`
  - `organizations -> OrganizationService`

### `get_service_registry(db: AsyncSession = Depends(get_db))`
Async FastAPI dependency generator that:
- Retrieves `ServiceRegistry.instance()`
- Creates a unique session id (`sess-<uuid>`)
- Binds the provided `AsyncSession` to `PostgresSessionRegistry` under that session id
- Sets the current session for the duration of the request
- Yields the `ServiceRegistry`
- Resets and unbinds the session on exit (in `finally`)

## Configuration/Dependencies
- Requires `ServiceRegistry.configure(...)` to be called during application startup.
- Relies on:
  - `fastapi.Depends`
  - `get_db` (provides `sqlalchemy.ext.asyncio.AsyncSession`)
  - `PostgresSessionRegistry.instance()` with methods:
    - `bind(session_id, db)`
    - `set_current_session(session_id)` returning a token
    - `reset_current_session(token)`
    - `unbind(session_id)`

## Usage

```python
from fastapi import APIRouter, Depends
from naas_abi.apps.nexus.apps.api.app.services.registry import (
    ServiceRegistry,
    RegistryServices,
    get_service_registry,
)

router = APIRouter()

# During startup (example; construct real service instances in your app):
# ServiceRegistry.configure(
#     RegistryServices(
#         iam=iam_service,
#         chat=chat_service,
#         search=search_service,
#         agents=agent_service,
#         workspaces=workspace_service,
#         organizations=org_service,
#     )
# )

@router.get("/me")
async def me(registry=Depends(get_service_registry)):
    # Access configured services through the registry
    return await registry.iam.get_current_user()
```

## Caveats
- `ServiceRegistry.instance()` raises `RuntimeError("ServiceRegistry is not configured")` if `configure()` was not called before request handling.
- `get_service_registry` is an async generator dependency; its session binding/unbinding happens per request via `PostgresSessionRegistry`.
