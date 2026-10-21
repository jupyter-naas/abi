# `SecretService`

## What it is
- An async service proxy for managing secrets in the `"secret"` domain.
- Provides basic CRUD-style operations: get, set, remove, and list.

## Public API
- `class SecretService(ServiceProxy)`
  - `domain = "secret"`: routes requests to the secret service domain.
  - `async def get(self, key: str, default: Any = None) -> str | Any`
    - Fetch a secret by `key`.
    - Returns `default` if the service returns `None`.
  - `async def set(self, key: str, value: str) -> None`
    - Store/update a secret value for `key`.
  - `async def remove(self, key: str) -> None`
    - Delete a secret by `key`.
  - `async def list(self) -> dict[str, str | None]`
    - Return all secrets as a mapping `{key: value}`.
    - Values may be `None`.

## Configuration/Dependencies
- Depends on `naas_abi_sdk.services._codec.ServiceProxy`.
  - Uses the inherited `self._request(...)` method to call service operations:
    - `"get"`, `"set"`, `"remove"`, `"list"`.

## Usage
```python
import asyncio
from naas_abi_sdk.services.secret import SecretService

async def main(secret: SecretService):
    await secret.set("API_KEY", "abc123")
    value = await secret.get("API_KEY")
    missing = await secret.get("DOES_NOT_EXIST", default="fallback")

    all_secrets = await secret.list()
    await secret.remove("API_KEY")

# SecretService construction depends on ServiceProxy wiring in your application.
# asyncio.run(main(secret_service_instance))
```

## Caveats
- `get()` returns `default` only when the underlying `"get"` request yields `None` (not when the key is missing vs. explicitly stored as `None`; behavior depends on the backend).
- `list()` expects the backend to return an iterable of entries shaped like `{"key": ..., "value": ...}`.
