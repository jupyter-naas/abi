# AgentSecondaryAdapterPostgres

## What it is
- An async PostgreSQL-backed persistence adapter implementing `AgentPersistencePort`.
- Uses SQLAlchemy `AsyncSession` to:
  - CRUD agent configurations (`AgentConfigModel`)
  - Fetch inference server records (`InferenceServerModel`)

## Public API

### Class: `AgentSecondaryAdapterPostgres(AgentPersistencePort)`
All methods are `async`.

- `__init__(db: AsyncSession | None = None, db_getter: Callable[[], AsyncSession | None] | None = None)`
  - Binds an `AsyncSession` directly (`db`) or lazily via `db_getter`.

- `db -> AsyncSession` (property)
  - Returns the bound session, or obtains it from `db_getter`.
  - Raises `RuntimeError` if no session is available.

- `list_by_workspace(workspace_id: str) -> list[AgentRecord]`
  - Lists all agents for a workspace.

- `get_by_id(agent_id: str) -> AgentRecord | None`
  - Fetches one agent by id.

- `get_inference_server(workspace_id: str, server_id: str) -> InferenceServerRecord | None`
  - Fetches an inference server by id, scoped to a workspace.

- `create(data: AgentCreateInput) -> AgentRecord`
  - Creates an agent with a generated UUID string id.
  - Commits and refreshes the created row.
  - On `IntegrityError`, rolls back and re-raises.

- `create_many(agents: list[AgentCreateInput]) -> list[AgentRecord]`
  - Bulk-creates agents.
  - Returns `[]` if input list is empty.
  - Commits once, then refreshes each created row.

- `update(agent_id: str, updates: AgentUpdateInput) -> AgentRecord | None`
  - Patch-updates supported fields.
  - Returns `None` if the agent does not exist.
  - If promoting `is_default=True`, demotes other defaults in the same workspace using `SELECT ... FOR UPDATE`.

- `delete(agent_id: str) -> bool`
  - Deletes an agent by id.
  - Returns `False` if not found; otherwise commits and returns `True`.

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
  - Provide either:
    - `db=AsyncSession`, or
    - `db_getter=Callable[[], AsyncSession | None]`

## Usage
```python
import asyncio
from sqlalchemy.ext.asyncio import AsyncSession

from naas_abi.apps.nexus.apps.api.app.services.agents.adapters.secondary.postgres import (
    AgentSecondaryAdapterPostgres,
)
from naas_abi.apps.nexus.apps.api.app.services.agents.port import AgentCreateInput

async def run(session: AsyncSession):
    repo = AgentSecondaryAdapterPostgres(db=session)

    created = await repo.create(
        AgentCreateInput(
            workspace_id="ws_1",
            name="My agent",
            class_name="MyAgent",
            module_path=None,
            description="Example",
            system_prompt="You are helpful.",
            model_id="model_1",
            provider="provider_x",
            logo_url=None,
            enabled=True,
        )
    )

    agents = await repo.list_by_workspace("ws_1")
    fetched = await repo.get_by_id(created.id)

    print(created.id, len(agents), fetched.name if fetched else None)

# asyncio.run(run(session))  # session must be provided by your application
```

## Caveats
- `db` property raises `RuntimeError` if neither `db` nor `db_getter` provides a session.
- `_to_record()` parses timestamps via `datetime.fromisoformat(str(model.created_at))` and `datetime.fromisoformat(str(model.updated_at))`; these fields must be string-serializable in ISO format.
- Optional string columns are normalized via `_opt_str()`:
  - `None`, `"None"`, and `"null"` (case-insensitive) are treated as absent (`None`) to avoid leaking `"None"` into consumers.
- `create()` rolls back on `IntegrityError` and re-raises (caller must handle).
- `create_many()` refreshes each row individually after commit (one refresh per inserted row).
