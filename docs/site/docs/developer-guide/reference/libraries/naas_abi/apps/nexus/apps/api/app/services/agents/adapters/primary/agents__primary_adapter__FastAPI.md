# AgentsFastAPIPrimaryAdapter

## What it is
A FastAPI primary adapter exposing CRUD + sync endpoints for workspace “agents”, backed by an `AgentService`. It also:
- Builds and caches a process-level registry of available in-process `Agent` classes (expensive dynamic imports, done once per API worker).
- Enriches listed agents with presentation/runtime fields derived from the in-memory class registry.
- Reconciles DB rows with discovered in-process agents and remotely discovered agents (via NATS discovery) through a `POST /sync` endpoint.
- Applies feature-flag-based filtering so callers may see different subsets of agents within the same workspace.

## Public API

### Class
- `AgentsFastAPIPrimaryAdapter`
  - `__init__()`: exposes `self.router` (module-level `APIRouter`).

### Dependency providers
- `get_agent_service(registry: ServiceRegistry = Depends(get_service_registry)) -> AgentService`
  - Returns the `AgentService` from the service registry.
- `request_context(current_user: User) -> RequestContext`
  - Builds a `RequestContext` with authenticated `TokenData` for service calls.

### FastAPI routes (mounted on `router`)
Router-level dependency: `Depends(get_current_user_required)` (authentication required).

- `GET /` → `list_agents(workspace_id: str | None = None) -> list[AgentRecord]`
  - Returns `[]` when `workspace_id` is missing.
  - Enforces workspace access; filters agents by caller feature flags.
  - Does **not** mutate DB.
  - Enriches each returned `AgentRecord` in-memory with:
    - `suggestions`, `logo_url`, `intents`
    - `module_path` (derived if missing)
    - `resolved_model_id` (effective model resolution)
    - `model_ids` (class-declared candidate model ids)

- `POST /sync` → `sync_agents(workspace_id: str | None = None) -> list[AgentRecord]`
  - Returns `[]` when `workspace_id` is missing.
  - Enforces workspace access; returns caller-scoped (feature-filtered) results.
  - Serializes sync per workspace within a worker via an `asyncio.Lock`.
  - Reconciles DB to match discovered agents:
    - Deduplicates rows sharing the same `class_name` (keeps canonical, deletes others)
    - Deletes stale non-remote class-backed rows missing from the in-process registry
    - Creates missing rows for newly discovered in-process agents (`provider="abi"`)
    - Creates missing rows for remotely discovered agents (`provider=REMOTE_PROVIDER`)
    - Backfills missing `module_path` on existing rows (persists)
    - Aligns `enabled` state to workspace roster/default unless `enabled_override` is set
    - Ensures the resolved default agent is enabled and marked `is_default=True`

- `POST /` → `create_agent(agent: AgentCreateInput) -> AgentRecord`
  - Enforces workspace access for `agent.workspace_id`.
  - Creates via `AgentService.create_agent`.

- `PATCH /{agent_id}` → `update_agent(agent_id: str, updates: AgentUpdateInput) -> AgentRecord`
  - 404 if not found.
  - Enforces workspace access of the existing agent.
  - Updates via `AgentService.update_agent` with:
    - `name`, `description`, `system_prompt`, `enabled`, `is_default`
    - `model_id` set from `updates.model`
    - `enabled_override` set to `updates.enabled` (manual toggle persists across later sync alignment)

- `DELETE /{agent_id}` → `delete_agent(agent_id: str) -> dict[str, str]`
  - 404 if not found.
  - Enforces workspace access.
  - Deletes via `AgentService.delete_agent`.
  - Returns `{"status": "deleted"}`.

- `GET /{agent_id}` → `get_agent(agent_id: str) -> AgentRecord`
  - 404 if not found.
  - Enforces workspace access.
  - Applies feature filtering; returns 404 if caller lacks access to that agent’s feature.
  - Returns the stored DB record (no enrichment).

### Other public helpers (non-route)
- `pick_workspace_chat_agent_id(agents: list[AgentRecord], requested_id: str | None) -> str | None`
  - Chooses a runnable chat agent id:
    - Uses requested id only if it exists in list and is enabled
    - Else prefers `is_default`, else enabled Nexus Abi orchestrator, else first enabled
- `pick_workspace_slides_agent_id(agents: list[AgentRecord]) -> str | None`
  - Returns enabled Nexus Slides agent id, or `None` (no fallback).
- `pick_workspace_documents_agent_id(agents: list[AgentRecord]) -> str | None`
  - Returns enabled Nexus Documents agent id, or `None`.
- `pick_workspace_sheets_agent_id(agents: list[AgentRecord]) -> str | None`
  - Returns enabled Nexus Sheets agent id, or `None`.

## Configuration/Dependencies
- FastAPI: `APIRouter`, `Depends`, `HTTPException`
- Authn/Authz:
  - `get_current_user_required`
  - `require_workspace_access(user_id, workspace_id)` (also returns role used for feature flags)
  - `User`
- Feature access filtering:
  - `caller_feature_flags(db, workspace_id, role)`
  - `filter_feature_agents(agent_list, flags)`
- Workspace seed / catalog:
  - `workspace_seed_for_slug`, `resolve_agent_ref`, `resolve_agent_refs`
- Services / models:
  - `ServiceRegistry`, `get_service_registry`
  - `AgentService`, `AgentCreateInput`, `AgentUpdateInput`, `AgentRecord`
  - `RequestContext`, `TokenData`
- Agent discovery:
  - In-process: `naas_abi.ABIModule.get_instance()` and engine modules’ `agents`
  - Remote: NATS discovery via `naas_abi.apps.nexus...services.agents.remote.factory.get_remote_agent_directory()`
  - Remote provider constant: `REMOTE_PROVIDER`
- Database access (internal helpers):
  - SQLAlchemy async session to resolve workspace slug
  - Handles `sqlalchemy.exc.IntegrityError` on concurrent inserts
- Public URL utilities for assets:
  - `public_modules_url`, `resolve_abi_module_path`, `resolve_module_public_asset_path`

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
- First `GET /agents/?workspace_id=...` in a worker may be slow: it builds the process-level agent class registry via dynamic imports; subsequent calls reuse the cached registry.
- `GET /agents/` and `POST /agents/sync` return `[]` (not an error) when `workspace_id` is omitted.
- `POST /agents/sync` mutates the database (dedupe/delete/create/backfill/enable-alignment) and is serialized per workspace only within the current API worker; cross-worker insert races are handled via a unique index and `IntegrityError` retry behavior.
- `GET /agents/{agent_id}` returns the stored record without enrichment fields added by listing/sync.
- Feature filtering can hide agents from callers; `GET /{agent_id}` returns 404 if the agent is not reachable under the caller’s feature flags (even if it exists).
