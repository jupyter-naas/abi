# AgentSecondaryAdapterPostgres

## What it is
- An async PostgreSQL-backed persistence adapter implementing `AgentPersistencePort`.
- Uses SQLAlchemy `AsyncSession` to CRUD agent configurations (`AgentConfigModel`) and to fetch inference server records (`InferenceServerModel`).

## Public API
### Class: `AgentSecondaryAdapterPostgres(AgentPersistencePort)`
Persistence adapter methods (all `async`):

- `__init__(db: AsyncSession | None = None, db_getter: Callable[[], AsyncSession | None] | None = None)`
  - Bind an `AsyncSession` directly (`db`) or lazily via `db_getter`.

- `list_by_workspace(workspace_id: str) -> list[AgentRecord]`
  - List all agents in a workspace.

- `get_by_id(agent_id: str) -> AgentRecord | None`
  - Fetch a single agent by id.

- `get_inference_server(workspace_id: str, server_id: str) -> InferenceServerRecord | None`
  - Fetch an inference server by id, scoped to a workspace.

- `create(data: AgentCreateInput) -> AgentRecord`
  - Create a new agent (generates a UUID string id).

- `create_many(agents: list[AgentCreateInput]) -> list[AgentRecord]`
  - Bulk-create agents; returns `[]` if input list is empty.

- `update(agent_id: str, updates: AgentUpdateInput) -> AgentRecord | None`
  - Patch-update supported fields; returns `None` if agent not found.

- `delete(agent_id: str) -> bool`
  - Delete an agent; returns `False` if not found.

### Property
- `db -> AsyncSession`
  - Returns the bound session, or obtains it from `db_getter`.
  - Raises `RuntimeError` if no session is available.

## Configuration/Dependencies
- Requires:
  - `sqlalchemy.ext.asyncio.AsyncSession`
  - SQLAlchemy models:
    - `AgentConfigModel`
    - `InferenceServerModel`
  - Port/types from `naas_abi.apps.nexus.apps.api.app.services.agents.port`:
    - `AgentPersistencePort`, `AgentCreateInput`, `AgentUpdateInput`
    - `AgentRecord`, `InferenceServerRecord`
- Database session binding:
  - Provide `db=AsyncSession` **or** `db_getter=Callable[[], AsyncSession | None]`.

## Usage
```python
import asyncio
from sqlalchemy.ext.asyncio import AsyncSession

from naas_abi.apps.nexus.apps.api.app.services.agents.adapters.secondary.postgres import (
    AgentSecondaryAdapterPostgres,
)
from naas_abi.apps.nexus.apps.api.app.services.agents.port import AgentCreateInput

async def main(session: AsyncSession):
    repo = AgentSecondaryAdapterPostgres(db=session)

    created = await repo.create(
        AgentCreateInput(
            workspace_id="ws_1",
            name="My agent",
            class_name="MyAgent",
            description="Example",
            system_prompt="You are helpful.",
            model_id="model_1",
            provider="provider_x",
            logo_url="https://example.com/logo.png",
            enabled=True,
        )
    )

    agents = await repo.list_by_workspace("ws_1")
    fetched = await repo.get_by_id(created.id)

    print(created.id, len(agents), fetched.name if fetched else None)

# asyncio.run(main(session))  # provide an AsyncSession from your app
```

## Caveats
- `db` property raises `RuntimeError` if neither `db` nor `db_getter` provides a session.
- `created_at`/`updated_at` are converted via `datetime.fromisoformat(str(...))`; underlying model values must be string-serializable in ISO format for conversion to succeed.
- `create_many()` commits once and then refreshes each created model (one refresh per row).
