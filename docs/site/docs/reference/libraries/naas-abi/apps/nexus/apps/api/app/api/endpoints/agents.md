# `agents` (Agents API endpoints)

## What it is
FastAPI router implementing agent management endpoints for a NEXUS workspace:
- CRUD for workspace-scoped custom agents stored in the database.
- “Sync” operation to create agents from either a centralized model registry or an ABI inference server.
- Read-only endpoints for built-in “default agents” (AIA/BOB/System).
- Best-effort discovery of ABI agents by inspecting loaded ABI modules and/or statically parsing `naas_abi/agents/*.py`.

## Public API

### FastAPI router
- `router: APIRouter`
  - All routes require authentication via `get_current_user_required`.

### Pydantic models (request/response)
- `AgentCapability`
  - Fields: `name`, `description`, `enabled=True`
- `AgentConfig`
  - Agent configuration returned by most endpoints.
  - Key fields: `id`, `name`, `agent_type`, `description`, `system_prompt`, `capabilities`, `model`, `provider`, `logo_url`, `enabled`, `temperature`, `max_tokens`, `created_at`, `updated_at`
- `AgentStatus`
  - Fields: `agent_id`, `status`, `last_activity`, `active_conversations`, `error_message`
- `ToolExecution`
  - Fields: `agent_id`, `tool_name`, `parameters`, `context`
- `ToolResult`
  - Fields: `success`, `result`, `error`, `execution_time_ms`
- `AgentCreate`
  - Request body for creating a custom agent.
- `AgentUpdate`
  - Request body for patching a custom agent.
- `AgentSyncResult`
  - Response for the sync operation.

### Endpoints
- `GET /`
  - `list_agents(workspace_id: str | None) -> list[AgentConfig]`
  - Returns `[]` when `workspace_id` is not provided.
  - Otherwise:
    - returns DB agents for workspace
    - appends discovered ABI agents (from loaded modules and from `naas_abi/agents`) if their *names* do not already exist in the DB list (case-insensitive).
- `POST /`
  - `create_agent(agent: AgentCreate) -> AgentConfig`
  - Creates a DB-backed custom agent (disabled by default).
- `PATCH /{agent_id}`
  - `update_agent(agent_id: str, updates: AgentUpdate) -> AgentConfig`
  - Updates DB-backed agent fields (`name`, `description`, `system_prompt`, `model`, `enabled`).
- `DELETE /{agent_id}`
  - `delete_agent(agent_id: str) -> dict[str, str]`
  - Deletes a DB-backed agent. Returns `{"status": "deleted"}`.
- `POST /sync`
  - `sync_agents_from_models(workspace_id: str, server_id: str | None = None) -> AgentSyncResult`
  - If `server_id` is provided:
    - loads the server from DB (must be `type == "abi"`)
    - requests `GET {server.endpoint}/agents` (Bearer auth if `server.api_key`)
    - creates disabled DB agents for returned items; skips if an agent with the same *name* already exists (case-insensitive).
  - If `server_id` is not provided:
    - uses `get_all_models()` and creates one agent per model not already present by `model_id`.
- `GET /{agent_id}`
  - `get_agent(agent_id: str) -> AgentConfig`
  - Returns a default agent if `agent_id` matches `{"aia","bob","system"}`, else fetches from DB.
- `GET /{agent_id}/status`
  - `get_agent_status(agent_id: str) -> AgentStatus`
  - Only supports default agents; returns a placeholder “active” status.
- `GET /{agent_id}/capabilities`
  - `get_agent_capabilities(agent_id: str) -> list[AgentCapability]`
  - Only supports default agents.
- `POST /{agent_id}/tools/execute`
  - `execute_tool(agent_id: str, execution: ToolExecution) -> ToolResult`
  - Only supports default agents; returns a placeholder “not yet implemented” message.

## Configuration/Dependencies
- Authentication/authorization:
  - `get_current_user_required` (router dependency)
  - `require_workspace_access(user_id, workspace_id)` (per workspace operations)
- Database:
  - `get_db() -> AsyncSession`
  - Models: `AgentConfigModel` (and `InferenceServerModel` during `/sync?server_id=...`)
- Model registry:
  - `get_all_models()`
  - `get_logo_for_provider(provider)`
- Optional ABI discovery:
  - Uses `naas_abi.ABIModule.get_instance()` (loaded modules) if available.
  - Also parses Python files under `naas_abi/agents` using `ast` without importing them.
- External HTTP (only for `/sync` with `server_id`):
  - `httpx.AsyncClient`

## Usage

### Mount the router in a FastAPI app
```python
from fastapi import FastAPI
from naas_abi.apps.nexus.apps.api.app.api.endpoints import agents

app = FastAPI()
app.include_router(agents.router, prefix="/agents", tags=["agents"])
```

### Example calls (HTTP)
```python
import requests

base = "http://localhost:8000"
headers = {"Authorization": "Bearer <token>"}

# List agents for a workspace
agents = requests.get(f"{base}/agents/", params={"workspace_id": "ws_123"}, headers=headers).json()

# Create a custom agent (disabled by default)
new_agent = requests.post(
    f"{base}/agents/",
    headers=headers,
    json={
        "workspace_id": "ws_123",
        "name": "My Agent",
        "description": "Custom assistant",
        "system_prompt": "You are helpful.",
        "model": "gpt-4",
        "temperature": 0.7,
        "max_tokens": 4096,
    },
).json()
```

## Caveats
- `GET /` returns an empty list unless `workspace_id` is provided.
- `PATCH /{agent_id}`:
  - `temperature` and `max_tokens` are accepted in the request model but are **not persisted** (response uses defaults `0.7` and `4096`).
  - `updated_at` is set with `datetime.now(UTC).replace(tzinfo=None)` (timezone info removed).
- Status and tool execution are placeholders:
  - `GET /{agent_id}/status` and `POST /{agent_id}/tools/execute` are only implemented for default agents and do not query/execute real runtime behavior.
- ABI agent discovery:
  - Best-effort and may be empty depending on environment.
  - Discovered agents are deduplicated by *name* (case-insensitive), not by `id`.
