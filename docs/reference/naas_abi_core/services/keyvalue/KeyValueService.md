# KeyValueService

## What it is
- A thin service wrapper around an `IKeyValueAdapter` implementation.
- Provides a simple key/value API (bytes values) by delegating all operations to the injected adapter.

## Public API
- **Class: `KeyValueService(adapter: IKeyValueAdapter)`**
  - Initializes the service with a concrete key/value adapter.

### Methods
- **`get(key: str) -> bytes`**
  - Retrieve the value for `key`.
- **`set(key: str, value: bytes, ttl: int | None = None) -> None`**
  - Store `value` at `key`, optionally with a TTL.
- **`set_if_not_exists(key: str, value: bytes, ttl: int | None = None) -> bool`**
  - Store only if `key` does not exist; returns whether the write occurred.
- **`delete(key: str) -> None`**
  - Delete `key`.
- **`delete_if_value_matches(key: str, value: bytes) -> bool`**
  - Delete `key` only if the current value matches; returns whether the delete occurred.
- **`exists(key: str) -> bool`**
  - Check whether `key` exists.

## Configuration/Dependencies
- Requires an implementation of **`IKeyValueAdapter`** from `naas_abi_core.services.keyvalue.KeyValuePorts`.
- Inherits from **`ServiceBase`** (`naas_abi_core.services.ServiceBase`).

## Usage
```python
from naas_abi_core.services.keyvalue.KeyValueService import KeyValueService
from naas_abi_core.services.keyvalue.KeyValuePorts import IKeyValueAdapter

class InMemoryAdapter(IKeyValueAdapter):
    def __init__(self):
        self.store = {}

    def get(self, key: str) -> bytes:
        return self.store[key]

    def set(self, key: str, value: bytes, ttl: int | None = None) -> None:
        self.store[key] = value

    def set_if_not_exists(self, key: str, value: bytes, ttl: int | None = None) -> bool:
        if key in self.store:
            return False
        self.store[key] = value
        return True

    def delete(self, key: str) -> None:
        self.store.pop(key, None)

    def delete_if_value_matches(self, key: str, value: bytes) -> bool:
        if self.store.get(key) == value:
            self.store.pop(key, None)
            return True
        return False

    def exists(self, key: str) -> bool:
        return key in self.store

svc = KeyValueService(InMemoryAdapter())
svc.set("k", b"v")
assert svc.get("k") == b"v"
assert svc.exists("k") is True
```

## Caveats
- All behavior (including TTL semantics, error handling, and missing-key behavior) is determined by the injected `IKeyValueAdapter`.
- Values are `bytes`; callers must encode/decode non-bytes types themselves.
