# KeyValueService

## What it is
- A small service wrapper around an `IKeyValueAdapter`.
- Provides a key/value API (get/set/delete/exists) while delegating all operations to the injected adapter.

## Public API
### Class: `KeyValueService`
- `__init__(adapter: IKeyValueAdapter)`
  - Stores the provided adapter; calls `ServiceBase` constructor.

- `get(key: str) -> bytes`
  - Returns the raw value for `key` from the adapter.

- `set(key: str, value: bytes, ttl: int | None = None) -> None`
  - Stores `value` at `key`, optionally with a TTL, via the adapter.

- `set_if_not_exists(key: str, value: bytes, ttl: int | None = None) -> bool`
  - Attempts to set only if `key` does not exist; returns adapter result.

- `delete(key: str) -> None`
  - Deletes `key` via the adapter.

- `delete_if_value_matches(key: str, value: bytes) -> bool`
  - Deletes `key` only if the stored value matches `value`; returns adapter result.

- `exists(key: str) -> bool`
  - Checks existence of `key` via the adapter.

## Configuration/Dependencies
- Depends on:
  - `naas_abi_core.services.keyvalue.KeyValuePorts.IKeyValueAdapter` (must implement the delegated methods).
  - `naas_abi_core.services.ServiceBase.ServiceBase` (base class; not configured here).
- No internal configuration; behavior is entirely determined by the adapter implementation.

## Usage
```python
from naas_abi_core.services.keyvalue.KeyValueService import KeyValueService
from naas_abi_core.services.keyvalue.KeyValuePorts import IKeyValueAdapter

class InMemoryAdapter(IKeyValueAdapter):
    def __init__(self):
        self._store = {}

    def get(self, key: str) -> bytes:
        return self._store[key]

    def set(self, key: str, value: bytes, ttl: int | None = None) -> None:
        self._store[key] = value

    def set_if_not_exists(self, key: str, value: bytes, ttl: int | None = None) -> bool:
        if key in self._store:
            return False
        self._store[key] = value
        return True

    def delete(self, key: str) -> None:
        self._store.pop(key, None)

    def delete_if_value_matches(self, key: str, value: bytes) -> bool:
        if self._store.get(key) == value:
            del self._store[key]
            return True
        return False

    def exists(self, key: str) -> bool:
        return key in self._store

svc = KeyValueService(InMemoryAdapter())
svc.set("k", b"v")
assert svc.get("k") == b"v"
assert svc.exists("k") is True
```

## Caveats
- All semantics (TTL handling, missing-key behavior, concurrency guarantees) are defined by the adapter; this service does not add validation or fallback behavior.
