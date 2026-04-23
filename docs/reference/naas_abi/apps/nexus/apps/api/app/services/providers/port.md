# ProviderAvailabilityPort

## What it is
- An abstract async "port" (interface) that defines how to query provider availability inputs:
  - Workspaces accessible to a user
  - Secret keys available for given workspaces
  - Environment keys available for given names

## Public API
- `class ProviderAvailabilityPort(ABC)`
  - `async list_workspace_ids_for_user(user_id: str) -> list[str]`
    - Return workspace IDs accessible by the given user.
  - `async list_secret_keys_for_workspaces(workspace_ids: list[str]) -> set[str]`
    - Return the set of secret keys available across the provided workspaces.
  - `async list_environment_keys(key_names: list[str]) -> set[str]`
    - Return the set of environment keys available among the provided key names.

## Configuration/Dependencies
- Uses Python standard library:
  - `abc.ABC`, `abc.abstractmethod`
- Async methods; intended to be implemented by an infrastructure/service adapter.

## Usage
```python
import asyncio
from naas_abi.apps.nexus.apps.api.app.services.providers.port import ProviderAvailabilityPort

class InMemoryProviderAvailability(ProviderAvailabilityPort):
    async def list_workspace_ids_for_user(self, user_id: str) -> list[str]:
        return ["ws-1", "ws-2"] if user_id == "user-1" else []

    async def list_secret_keys_for_workspaces(self, workspace_ids: list[str]) -> set[str]:
        return {"OPENAI_API_KEY"} if "ws-1" in workspace_ids else set()

    async def list_environment_keys(self, key_names: list[str]) -> set[str]:
        existing = {"PATH", "HOME"}
        return set(key_names) & existing

async def main() -> None:
    port = InMemoryProviderAvailability()
    ws_ids = await port.list_workspace_ids_for_user("user-1")
    secrets = await port.list_secret_keys_for_workspaces(ws_ids)
    env_keys = await port.list_environment_keys(["PATH", "MISSING"])
    print(ws_ids, secrets, env_keys)

asyncio.run(main())
```

## Caveats
- This module defines only an interface; using it requires providing a concrete implementation.
- All methods are `async`; callers must await them in an async context.
