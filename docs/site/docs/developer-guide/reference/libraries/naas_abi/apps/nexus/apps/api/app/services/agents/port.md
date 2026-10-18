# AgentPersistencePort

## What it is
- A persistence **port/interface** for managing **agent** records and retrieving **inference server** configuration.
- Defines dataclasses used as stored records and as inputs for create/update operations.
- Intended to be implemented by an adapter (e.g., database, external service).

## Public API

### Data models (dataclasses)
- `AgentRecord`
  - Persisted/returned representation of an agent.
  - Fields:
    - Required: `id`, `workspace_id`, `name`, `description`, `enabled`, `created_at`, `updated_at`
    - Optional metadata: `class_name`, `module_path`, `system_prompt`, `model_id`, `provider`, `logo_url`
    - Flags/lists: `is_default` (default `False`), `suggestions`, `intents`
    - Non-persisted/effective fields (noted in comments): `resolved_model_id`, `model_ids`, `enabled_override`

- `InferenceServerRecord`
  - Inference server configuration record.
  - Fields: `id`, `workspace_id`, `name`, `type`, `endpoint`, `api_key` (nullable)

- `AgentCreateInput`
  - Input payload for creating an agent.
  - Fields: `workspace_id`, `name`, and optional `class_name`, `module_path`, `description`, `system_prompt`, `model_id`, `provider`, `logo_url`, `enabled` (default `False`)

- `AgentUpdateInput`
  - Input payload for updating an agent (all optional).
  - Fields: `name`, `class_name`, `module_path`, `description`, `system_prompt`, `model_id`, `logo_url`, `enabled`, `is_default`, `model`, `enabled_override`

### Port (abstract interface)
- `class AgentPersistencePort(ABC)`
  - `async list_by_workspace(workspace_id: str) -> list[AgentRecord]`
    - Return all agents for a workspace.
  - `async get_by_id(agent_id: str) -> AgentRecord | None`
    - Return agent by id (or `None` if not found).
  - `async get_inference_server(workspace_id: str, server_id: str) -> InferenceServerRecord | None`
    - Return inference server config for a workspace (or `None`).
  - `async create(data: AgentCreateInput) -> AgentRecord`
    - Create and return a single agent record.
  - `async create_many(agents: list[AgentCreateInput]) -> list[AgentRecord]`
    - Create and return multiple agent records.
  - `async update(agent_id: str, updates: AgentUpdateInput) -> AgentRecord | None`
    - Update and return an agent (or `None` if not found).
  - `async delete(agent_id: str) -> bool`
    - Delete an agent; return success flag.

## Configuration/Dependencies
- Standard library only:
  - `abc.ABC`, `abc.abstractmethod`
  - `dataclasses.dataclass`
  - `datetime.datetime`
- All port methods are **async**; implementations must be usable in an async runtime.

## Usage

Minimal in-memory implementation example:

```python
import asyncio
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

    async def get_inference_server(
        self, workspace_id: str, server_id: str
    ) -> InferenceServerRecord | None:
        return None

    async def create(self, data: AgentCreateInput) -> AgentRecord:
        now = datetime.utcnow()
        agent_id = f"agent_{len(self._agents)+1}"
        record = AgentRecord(
            id=agent_id,
            workspace_id=data.workspace_id,
            name=data.name,
            description=data.description or "",
            enabled=data.enabled,
            class_name=data.class_name,
            module_path=data.module_path,
            system_prompt=data.system_prompt,
            model_id=data.model_id,
            provider=data.provider,
            logo_url=data.logo_url,
            created_at=now,
            updated_at=now,
        )
        self._agents[agent_id] = record
        return record

    async def create_many(self, agents: list[AgentCreateInput]) -> list[AgentRecord]:
        return [await self.create(a) for a in agents]

    async def update(self, agent_id: str, updates: AgentUpdateInput) -> AgentRecord | None:
        existing = self._agents.get(agent_id)
        if existing is None:
            return None
        patch = {k: v for k, v in updates.__dict__.items() if v is not None}
        new = AgentRecord(**{**existing.__dict__, **patch}, updated_at=datetime.utcnow())
        self._agents[agent_id] = new
        return new

    async def delete(self, agent_id: str) -> bool:
        return self._agents.pop(agent_id, None) is not None

async def main():
    store = InMemoryAgentPersistence()
    agent = await store.create(AgentCreateInput(workspace_id="ws1", name="Support bot"))
    agent = await store.update(agent.id, AgentUpdateInput(enabled=True))
    print(agent.id, agent.enabled)

asyncio.run(main())
```

## Caveats
- `AgentRecord.resolved_model_id`, `AgentRecord.model_ids`, and `AgentRecord.enabled_override` are described in comments as API-layer/effective fields; this module does not enforce persistence behavior for them.
- `AgentUpdateInput.model` exists but this module does not define how it should be applied relative to `model_id`.
