# AgentsFastAPIPrimaryAdapter (Agents FastAPI primary adapter)

## What it is
A FastAPI router adapter that exposes CRUD endpoints for “agents” and auto-discovers available agent classes. On first `/` list call, it builds and caches a process-level registry of agent classes (expensive dynamic imports) and persists any newly discovered classes into the backend database.

## Public API

### Class
- `AgentsFastAPIPrimaryAdapter`
  - `__init__()`: exposes `self.router` (a shared module-level `APIRouter`).

### Dependency providers / helpers
- `get_agent_service(registry: ServiceRegistry = Depends(get_service_registry)) -> AgentService`  
  Returns the `AgentService` from the service registry.
- `request_context(current_user: User) -> RequestContext`  
  Builds a `RequestContext` with authenticated `TokenData` for service calls.

### Internal (module-private) helpers
- `_get_agent_class_registry() -> dict[str, type[Agent]]`  
  Lazily builds a process-level mapping `{ "<module>/<ClassName>": AgentClass }` using double-checked locking.
- `_extract_agent_suggestions(agent_cls: type) -> list[dict[str, str]] | None`  
  Normalizes `agent_cls.suggestions` (list of `{"label": str, "value": str}`).
- `_get_agent_class_name(agent_cls: type) -> str | None`  
  Reads `agent_cls.name` or fallback `agent_cls.NAME` if `name` is a `property`.
- `_get_agent_class_description(agent_cls: type) -> str | None`  
  Reads `agent_cls.description` or fallback `agent_cls.DESCRIPTION` if `description` is a `property`.
- `_get_agent_system_prompt(agent_cls: type) -> str | None`  
  Uses `agent_cls.system_prompt` if present; otherwise returns default from `naas_abi_core.services.agent.Agent.AgentConfiguration`.
- `_extract_agent_intents(agent_cls: type) -> list[dict[str, str]] | None`  
  Normalizes `agent_cls.intents` items with attributes `intent_value`, `intent_type`, optional `intent_target`, `intent_scope`.

### FastAPI routes (mounted on `router`)
All routes require authentication via `Depends(get_current_user_required)` (router-level dependency).

- `GET /` → `list_agents(workspace_id: str | None = None) -> list[AgentRecord]`
  - If `workspace_id` is missing: returns `[]`.
  - Enforces workspace access.
  - Lists agents from DB, discovers agent classes (cached), creates missing DB records, and enriches returned records with:
    - `suggestions` (from class)
    - `logo_url` (from class attribute)
    - `intents` (from class)
  - New agents are created with:
    - `provider="abi"`
    - `enabled=True` only when discovered class name resolves to `"Abi"`.

- `POST /` → `create_agent(agent: AgentCreateInput) -> AgentRecord`
  - Enforces workspace access for `agent.workspace_id`.
  - Creates an agent via `AgentService.create_agent`.

- `PATCH /{agent_id}` → `update_agent(agent_id: str, updates: AgentUpdateInput) -> AgentRecord`
  - 404 if agent not found.
  - Enforces workspace access of the existing agent.
  - Updates via `AgentService.update_agent` mapping:
    - `name`, `description`, `system_prompt`, `enabled`
    - `model_id` is set from `updates.model`

- `DELETE /{agent_id}` → `delete_agent(agent_id: str) -> dict[str, str]`
  - 404 if agent not found.
  - Enforces workspace access.
  - Deletes via `AgentService.delete_agent`.
  - Returns `{"status": "deleted"}`.

- `GET /{agent_id}` → `get_agent(agent_id: str) -> AgentRecord`
  - 404 if agent not found.
  - Enforces workspace access.
  - Returns the DB record (no enrichment here).

## Configuration/Dependencies
- FastAPI:
  - `APIRouter`, `Depends`, `HTTPException`
- Auth & authorization:
  - `get_current_user_required` (authentication)
  - `require_workspace_access(user_id, workspace_id)` (authorization)
  - `User` model from auth endpoint module
- Services / models:
  - `ServiceRegistry`, `get_service_registry`
  - `AgentService`, `AgentCreateInput`, `AgentUpdateInput`, `AgentRecord`
  - `RequestContext`, `TokenData`
- Agent discovery:
  - `naas_abi.ABIModule.get_instance()`
  - `naas_abi_core.services.agent.Agent.Agent` (type for registry)
- Logging:
  - `naas_abi_core.logger`
- Threading:
  - Uses a process-level `threading.Lock` to protect the first registry build.

## Usage

### Mount the router in a FastAPI app
```python
from fastapi import FastAPI
from naas_abi.apps.nexus.apps.api.app.services.agents.adapters.primary.agents__primary_adapter__FastAPI import (
    AgentsFastAPIPrimaryAdapter,
)

app = FastAPI()
adapter = AgentsFastAPIPrimaryAdapter()

app.include_router(adapter.router, prefix="/agents", tags=["agents"])
```

## Caveats
- The first call to `GET /?workspace_id=...` may be slow because it dynamically imports and indexes all agent classes; subsequent calls reuse the cached registry.
- `GET /` returns an empty list when `workspace_id` is not provided (no error).
- `GET /{agent_id}` does not apply the enrichment (suggestions/logo/intents) that `GET /` performs.
