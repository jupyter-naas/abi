# AgentService

## What it is
- An application service that manages **Agents** and **Inference Servers** via a persistence adapter.
- Enforces authorization:
  - Scope checks (e.g., `agent.read`, `agent.create`)
  - Workspace access checks (requires `workspace.read`)

## Public API
### Class: `AgentService`
Constructor:
- `AgentService(adapter: AgentPersistencePort, iam_service: IAMService | None = None)`
  - `adapter`: persistence port used for all data access/mutations
  - `iam_service`: optional IAM integration used by authorization helpers

Methods (all async unless noted):
- `list_workspace_agents(context: RequestContext, workspace_id: str) -> list[AgentRecord]`
  - List agents for a workspace.
  - Requires scope: `agent.read` + workspace access.

- `get_agent(context: RequestContext, agent_id: str) -> AgentRecord | None`
  - Fetch an agent by ID.
  - Requires scope: `agent.read`.
  - If found, also requires workspace access for the agent’s workspace.

- `get_inference_server(context: RequestContext, workspace_id: str, server_id: str) -> InferenceServerRecord | None`
  - Fetch an inference server record by workspace + server ID.
  - Requires scope: `agent.read` + workspace access.

- `create_agent(context: RequestContext, data: AgentCreateInput) -> AgentRecord`
  - Create a single agent.
  - Requires scope: `agent.create` + workspace access for `data.workspace_id`.

- `create_agents(context: RequestContext, agents: list[AgentCreateInput]) -> list[AgentRecord]`
  - Bulk create agents.
  - Requires scope: `agent.create` + workspace access for each agent’s `workspace_id`.

- `update_agent(context: RequestContext, agent_id: str, updates: AgentUpdateInput) -> AgentRecord | None`
  - Update an agent by ID.
  - Requires scope: `agent.update`.
  - If the agent exists, requires workspace access for the existing agent’s workspace.
  - Returns whatever the adapter returns (may be `None`).

- `delete_agent(context: RequestContext, agent_id: str) -> bool`
  - Delete an agent by ID.
  - Requires scope: `agent.delete`.
  - If the agent exists, requires workspace access for the existing agent’s workspace.
  - Returns adapter result (boolean).

## Configuration/Dependencies
- Depends on ports/types from `naas_abi.apps.nexus.apps.api.app.services.agents.port`:
  - `AgentPersistencePort`, `AgentCreateInput`, `AgentUpdateInput`, `AgentRecord`, `InferenceServerRecord`
- Authorization helpers:
  - `ensure_scope` and `ensure_workspace_access`
- IAM integration:
  - `IAMService` (optional), `RequestContext` is required for all operations.

## Usage
```python
import asyncio

from naas_abi.apps.nexus.apps.api.app.services.agents.service import AgentService

async def main(adapter, context, workspace_id: str):
    svc = AgentService(adapter=adapter, iam_service=None)
    agents = await svc.list_workspace_agents(context, workspace_id)
    print(agents)

# asyncio.run(main(adapter, context, "ws_123"))
```

## Caveats
- Authorization is enforced inside each method:
  - Missing required scope will deny access.
  - Workspace access is validated for the relevant workspace; for `get/update/delete`, the workspace is derived from the existing agent record (if found).
- This service delegates all persistence behavior (including `None`/`bool` semantics) to the provided `AgentPersistencePort` implementation.
