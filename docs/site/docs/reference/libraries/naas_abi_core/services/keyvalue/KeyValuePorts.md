# KeyValuePorts

## What it is
Defines the key-value storage *port* (interface) used by the service layer, plus a dedicated exception for missing keys. Implementations of this port provide the actual backend (e.g., Redis, in-memory, etc.).

## Public API
- `class KVNotFoundError(Exception)`
  - Exception intended to signal that a key was not found.

- `class IKeyValueAdapter(abc.ABC)`
  - Abstract interface that key-value adapters must implement:
  - `get(self, key: str) -> bytes`
    - Retrieve the value for `key` as bytes.
  - `set(self, key: str, value: bytes, ttl: int | None = None) -> None`
    - Store `value` under `key`, optionally with a TTL (time-to-live).
  - `set_if_not_exists(self, key: str, value: bytes, ttl: int | None = None) -> bool`
    - Store `value` only if `key` does not already exist; returns whether it was set.
  - `delete(self, key: str) -> None`
    - Delete `key`.
  - `delete_if_value_matches(self, key: str, value: bytes) -> bool`
    - Delete `key` only if its current value matches `value`; returns whether deletion occurred.
  - `exists(self, key: str) -> bool`
    - Check whether `key` exists.

## Configuration/Dependencies
- Uses the Python standard library `abc` module (`ABC`, `abstractmethod`).
- Type hints use the Python 3.10+ union syntax (`int | None`).

## Usage
Implement the interface in your adapter:

```python
from naas_abi_core.services.keyvalue.KeyValuePorts import IKeyValueAdapter, KVNotFoundError

class InMemoryKV(IKeyValueAdapter):
    def __init__(self):
        self._data: dict[str, bytes] = {}

    def get(self, key: str) -> bytes:
        try:
            return self._data[key]
        except KeyError as e:
            raise KVNotFoundError(key) from e

    def set(self, key: str, value: bytes, ttl: int | None = None) -> None:
        self._data[key] = value  # ttl ignored in this simple example

    def set_if_not_exists(self, key: str, value: bytes, ttl: int | None = None) -> bool:
        if key in self._data:
            return False
        self._data[key] = value
        return True

    def delete(self, key: str) -> None:
        self._data.pop(key, None)

    def delete_if_value_matches(self, key: str, value: bytes) -> bool:
        if self._data.get(key) == value:
            del self._data[key]
            return True
        return False

    def exists(self, key: str) -> bool:
        return key in self._data
```

## Caveats
- This module only defines an interface; actual behavior (including TTL handling and when `KVNotFoundError` is raised) is determined by the adapter implementation.
