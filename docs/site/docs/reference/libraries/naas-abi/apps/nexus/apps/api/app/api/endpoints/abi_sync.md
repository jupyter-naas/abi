# abi_sync

## What it is
FastAPI endpoints and helpers to **discover** agents exposed by an external ABI server (via its `openapi.json`) and to **sync** those agents into a workspace as `AgentConfigModel` records.

## Public API

- `router: fastapi.APIRouter`
  - Registers the endpoints below.

- `class ABISyncResult(pydantic.BaseModel)`
  - Response model for sync results.
  - Fields:
    - `server_id: str`
    - `server_name: str`
    - `agents_discovered: int`
    - `agents_created: int`
    - `agents_updated: int`
    - `agents: list[str]` (agent names)

- `async def discover_abi_agents(endpoint: str, api_key: str | None = None) -> list[dict]`
  - Fetches `GET {endpoint}/openapi.json` and extracts agent-like routes.
  - Discovers paths that include both `"/agents/"` and `"/stream-completion"`.
  - Returns a list of dicts like:
    - `name`: derived from the path segment after `/agents/`
    - `description`: `description` from the `POST` operation for that path
    - `model_id`: `name` with spaces replaced by underscores
    - `endpoint_path`: the matched OpenAPI path

- `POST /workspaces/{workspace_id}/abi-servers/{server_id}/sync` → `ABISyncResult`
  - Handler: `async def sync_abi_agents(...)`
  - Discovers agents from the ABI server and **creates/updates** `AgentConfigModel` rows in the given workspace.
  - New agents are created with:
    - `provider="abi"`
    - `enabled=False` (must be enabled manually elsewhere)
    - `system_prompt=f"You are {name}. {description}"`
    - `id` format: `agent-abi-{server_id}-{model_id}`

- `GET /workspaces/{workspace_id}/abi-servers/{server_id}/discover` → `list[dict]`
  - Handler: `async def discover_abi_server_agents(...)`
  - Discovers agents from the ABI server without writing to the database (preview).

## Configuration/Dependencies

- **Auth / access control**
  - `get_current_user_required` (FastAPI dependency) provides `current_user: User`.
  - `require_workspace_access(current_user.id, workspace_id)` is enforced in both endpoints.

- **Database**
  - `db: sqlalchemy.ext.asyncio.AsyncSession` via `Depends(get_db)`.
  - Reads:
    - `InferenceServerModel` filtered by `id`, `workspace_id`, and `type == "abi"`.
  - Writes:
    - `AgentConfigModel` created/updated; commits once at end.

- **Networking**
  - `httpx.AsyncClient(timeout=30.0)` to fetch `{endpoint}/openapi.json`.

- **Time handling**
  - Uses `datetime.now(UTC).replace(tzinfo=None)` for `created_at`/`updated_at` (naive datetime).

## Usage

### Call discovery helper directly (async)
```python
import asyncio
from naas_abi.apps.nexus.apps.api.app.api.endpoints.abi_sync import discover_abi_agents

async def main():
    agents = await discover_abi_agents("https://abi-example.yourcompany.com")
    print(agents)

asyncio.run(main())
```

### HTTP (assuming this router is included in your FastAPI app)
- Discover (preview):
  - `GET /workspaces/{workspace_id}/abi-servers/{server_id}/discover`
- Sync into workspace:
  - `POST /workspaces/{workspace_id}/abi-servers/{server_id}/sync`

## Caveats

- `api_key` is accepted by `discover_abi_agents` but is **not used** in the HTTP request headers/params in this implementation.
- Agent discovery is heuristic: it matches any OpenAPI path containing both `"/agents/"` and `"/stream-completion"` and derives the agent name from the third `/`-separated segment.
- Newly created agents are **disabled by default** (`enabled=False`).
- Sync requires the `InferenceServerModel` to exist, match workspace, be of type `"abi"`, and be `enabled=True` (otherwise returns `404` or `400`).
