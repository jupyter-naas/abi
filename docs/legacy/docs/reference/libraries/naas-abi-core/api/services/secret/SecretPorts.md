# SecretPorts

## What it is
- Defines interfaces (“ports”) for a secret management system.
- Provides:
  - A custom exception for authentication failures.
  - Two abstract base classes (ABCs) describing required methods for secret adapters and services.

## Public API

### `SecretAuthenticationError`
- `class SecretAuthenticationError(Exception)`
- Purpose: signal authentication-related failures when accessing secrets (no behavior beyond standard `Exception`).

### `ISecretAdapter`
- `class ISecretAdapter(ABC)`
- Purpose: contract for a concrete secret backend adapter (e.g., env vars, vault, etc.).

Methods:
- `get(self, key: str, default: Any = None) -> str | Any | None`
  - Retrieve a secret by key; return `default` or `None` when not found (as defined by implementation).
- `set(self, key: str, value: str)`
  - Store/update a secret value for a key.
- `remove(self, key: str)`
  - Delete a secret by key.
- `list(self) -> Dict[str, str | None]`
  - Return a mapping of keys to values (or `None`), per implementation.

### `ISecretService`
- `class ISecretService(ABC)`
- Purpose: contract for a service layer that manages secrets, potentially across one or more adapters.

Attributes:
- `__adapter: List[ISecretAdapter]`
  - Declared type for internal adapter storage (actual wiring/usage is implementation-specific).

Methods:
- `get(self, key: str, default: Any = None) -> str | Any | None`
- `set(self, key: str, value: str)`
- `remove(self, key: str)`
- `list(self) -> Dict[str, str | None]`

## Configuration/Dependencies
- Standard library only:
  - `abc` (`ABC`, `abstractmethod`)
  - `typing` (`Any`, `Dict`, `List`)
- Python 3.10+ typing syntax is used (`str | Any | None`).

## Usage

```python
from typing import Any, Dict
from naas_abi_core.services.secret.SecretPorts import ISecretAdapter

class InMemorySecretAdapter(ISecretAdapter):
    def __init__(self):
        self._data: Dict[str, str] = {}

    def get(self, key: str, default: Any = None):
        return self._data.get(key, default)

    def set(self, key: str, value: str):
        self._data[key] = value

    def remove(self, key: str):
        self._data.pop(key, None)

    def list(self) -> Dict[str, str | None]:
        return dict(self._data)

adapter = InMemorySecretAdapter()
adapter.set("API_KEY", "secret")
print(adapter.get("API_KEY"))
print(adapter.list())
adapter.remove("API_KEY")
print(adapter.get("API_KEY", default="missing"))
```

## Caveats
- These are interfaces only; instantiating `ISecretAdapter` or `ISecretService` directly will fail due to abstract methods.
- `ISecretService.list()` contains a duplicated `raise NotImplementedError()` after the first one; it has no practical effect beyond being redundant.
