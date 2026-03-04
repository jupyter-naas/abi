# KeyValuePorts

## What it is
- Defines a minimal key-value storage interface (`IKeyValueAdapter`) for adapters to implement.
- Provides a specific exception (`KVNotFoundError`) for missing keys.

## Public API
- **`KVNotFoundError(Exception)`**
  - Exception type intended to represent “key not found” cases.

- **`IKeyValueAdapter(ABC)`** (abstract base class)
  - **`get(key: str) -> bytes`**
    - Retrieve the value for `key` as raw bytes.
  - **`set(key: str, value: bytes, ttl: int | None = None) -> None`**
    - Store `value` under `key`, optionally with a TTL.
  - **`set_if_not_exists(key: str, value: bytes, ttl: int | None = None) -> bool`**
    - Store only if `key` does not exist; returns whether the value was set.
  - **`delete(key: str) -> None`**
    - Delete `key`.
  - **`delete_if_value_matches(key: str, value: bytes) -> bool`**
    - Delete `key` only if its current value matches; returns whether deletion occurred.
  - **`exists(key: str) -> bool`**
    - Check if `key` exists.

## Configuration/Dependencies
- Uses Python standard library:
  - `abc.ABC`, `abc.abstractmethod`
- Type hint uses `int | None` (requires Python 3.10+).

## Usage
```python
from naas_abi_core.services.keyvalue.KeyValuePorts import IKeyValueAdapter, KVNotFoundError

class InMemoryKV(IKeyValueAdapter):
    def __init__(self):
        self._store: dict[str, bytes] = {}

    def get(self, key: str) -> bytes:
        if key not in self._store:
            raise KVNotFoundError(key)
        return self._store[key]

    def set(self, key: str, value: bytes, ttl: int | None = None) -> None:
        self._store[key] = value  # ttl ignored in this simple example

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

kv = InMemoryKV()
kv.set("a", b"1")
assert kv.get("a") == b"1"
```

## Caveats
- `IKeyValueAdapter` is an interface only; concrete behavior (including TTL handling and when to raise `KVNotFoundError`) is defined by implementations.
