# AgentPersistencePort

## What it is
- An abstract persistence interface (“port”) for managing **agents** and retrieving **inference server** configuration.
- Defines dataclasses used as records and inputs for create/update operations.

## Public API

### Data models
- `AgentRecord`
  - Represents an agent as stored/returned by persistence.
  - Fields include: `id`, `workspace_id`, `name`, `description`, `enabled`, `class_name`, `system_prompt`, `model_id`, `provider`, `logo_url`, `created_at`, `updated_at`, optional `suggestions`, `intents`.

- `InferenceServerRecord`
  - Represents an inference server configuration.
  - Fields: `id`, `workspace_id`, `name`, `type`, `endpoint`, `api_key`.

- `AgentCreateInput`
  - Input payload for creating an agent.
  - Fields: `workspace_id`, `name`, optional `class_name`, `description`, `system_prompt`, `model_id`, `provider`, `logo_url`, `enabled` (default `False`).

- `AgentUpdateInput`
  - Input payload for updating an agent.
  - Optional fields: `name`, `class_name`, `description`, `system_prompt`, `model_id`, `enabled`, `model`.

### Port (interface)
- `class AgentPersistencePort(ABC)`
  - `async list_by_workspace(workspace_id: str) -> list[AgentRecord]`
    - List agents for a workspace.
  - `async get_by_id(agent_id: str) -> AgentRecord | None`
    - Fetch an agent by its id.
  - `async get_inference_server(workspace_id: str, server_id: str) -> InferenceServerRecord | None`
    - Fetch inference server config for a workspace.
  - `async create(data: AgentCreateInput) -> AgentRecord`
    - Create a single agent.
  - `async create_many(agents: list[AgentCreateInput]) -> list[AgentRecord]`
    - Create multiple agents in one call.
  - `async update(agent_id: str, updates: AgentUpdateInput) -> AgentRecord | None`
    - Update an agent; returns updated record or `None` if not found.
  - `async delete(agent_id: str) -> bool`
    - Delete an agent; returns success flag.

## Configuration/Dependencies
- Standard library only:
  - `dataclasses.dataclass`
  - `datetime.datetime`
  - `abc.ABC`, `abc.abstractmethod`
- All port methods are **async**; implementations must be awaitable and run in an async environment.

## Usage

Implement the port in an adapter (e.g., database-backed). Minimal stub example:

```python
from datetime import datetime
from naas_abi.apps.nexus.apps.api.app.services.agents.port import (
    AgentPersistencePort,
    AgentCreateInput,
    AgentUpdateInput,
    AgentRecord,
    InferenceServerRecord,
)

class InMemoryAgentPersistence(AgentPersistencePort):
    def __init__(self):
        self._agents: dict[str, AgentRecord] = {}

    async def list_by_workspace(self, workspace_id: str) -> list[AgentRecord]:
        return [a for a in self._agents.values() if a.workspace_id == workspace_id]

    async def get_by_id(self, agent_id: str) -> AgentRecord | None:
        return self._agents.get(agent_id)

    async def get_inference_server(self, workspace_id: str, server_id: str) -> InferenceServerRecord | None:
        return None

    async def create(self, data: AgentCreateInput) -> AgentRecord:
        now = datetime.utcnow()
        record = AgentRecord(
            id=f"agent_{len(self._agents)+1}",
            workspace_id=data.workspace_id,
            name=data.name,
            description=data.description or "",
            enabled=data.enabled,
            class_name=data.class_name,
            system_prompt=data.system_prompt,
            model_id=data.model_id,
            provider=data.provider,
            logo_url=data.logo_url,
            created_at=now,
            updated_at=now,
        )
        self._agents[record.id] = record
        return record

    async def create_many(self, agents: list[AgentCreateInput]) -> list[AgentRecord]:
        return [await self.create(a) for a in agents]

    async def update(self, agent_id: str, updates: AgentUpdateInput) -> AgentRecord | None:
        existing = self._agents.get(agent_id)
        if not existing:
            return None
        new = AgentRecord(
            **{**existing.__dict__, **{k: v for k, v in updates.__dict__.items() if v is not None}},
            updated_at=datetime.utcnow(),
        )
        self._agents[agent_id] = new
        return new

    async def delete(self, agent_id: str) -> bool:
        return self._agents.pop(agent_id, None) is not None
```

## Caveats
- `AgentUpdateInput` includes both `model_id` and `model`; this module does not define how `model` should be applied.
- `AgentRecord.description` is required on the record, while `AgentCreateInput.description` is optional; adapters must decide how to handle missing descriptions.
