# SecretPorts

## What it is
Abstract interfaces (ports) for a secret storage system:
- `ISecretAdapter`: defines how a backend secret store is accessed.
- `ISecretService`: defines the service layer API built on top of one or more adapters.
- `SecretAuthenticationError`: exception type for authentication-related secret access errors.

## Public API
- **`SecretAuthenticationError(Exception)`**
  - Raised to signal authentication problems when interacting with secret storage.

- **`ISecretAdapter(ABC)`** (interface)
  - `get(key: str, default: Any = None) -> str | Any | None`: Retrieve a secret value by key.
  - `set(key: str, value: str) -> None`: Store a secret value by key.
  - `remove(key: str) -> None`: Delete a secret by key.
  - `list() -> Dict[str, str | None]`: List available secrets as a mapping of keys to values (or `None`).

- **`ISecretService(ABC)`** (interface)
  - `get(key: str, default: Any = None) -> str | Any | None`: Retrieve a secret via the service.
  - `set(key: str, value: str) -> None`: Store a secret via the service.
  - `remove(key: str) -> None`: Delete a secret via the service.
  - `list() -> Dict[str, str | None]`: List secrets via the service.
  - Internal attribute annotation: `__adapter: List[ISecretAdapter]` (intended to represent underlying adapters).

## Configuration/Dependencies
- Standard library only:
  - `abc.ABC`, `abc.abstractmethod`
  - `typing.Any`, `typing.Dict`, `typing.List`
- No runtime configuration is defined in this module.

## Usage
Implement the interfaces to create concrete adapters/services.

```python
from typing import Any, Dict
from naas_abi_core.services.secret.SecretPorts import ISecretAdapter, ISecretService

class InMemorySecretAdapter(ISecretAdapter):
    def __init__(self):
        self._store: Dict[str, str] = {}

    def get(self, key: str, default: Any = None) -> str | Any | None:
        return self._store.get(key, default)

    def set(self, key: str, value: str):
        self._store[key] = value

    def remove(self, key: str):
        self._store.pop(key, None)

    def list(self) -> Dict[str, str | None]:
        return dict(self._store)

class SecretService(ISecretService):
    def __init__(self, adapter: ISecretAdapter):
        self._adapter = adapter

    def get(self, key: str, default: Any = None):
        return self._adapter.get(key, default)

    def set(self, key: str, value: str):
        self._adapter.set(key, value)

    def remove(self, key: str):
        self._adapter.remove(key)

    def list(self):
        return self._adapter.list()

svc = SecretService(InMemorySecretAdapter())
svc.set("API_KEY", "secret")
print(svc.get("API_KEY"))
print(svc.list())
```

## Caveats
- This module defines **interfaces only**; it provides no concrete secret storage implementation.
- Method return types allow `str | Any | None` for `get()`, so callers should handle non-string defaults and missing keys.
- `ISecretService` contains a private attribute annotation `__adapter` but does not define how adapters are managed; concrete implementations must decide.
