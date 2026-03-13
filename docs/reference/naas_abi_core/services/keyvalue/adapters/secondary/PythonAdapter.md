# PythonAdapter

## What it is
- An in-memory, thread-safe key/value adapter implementing `IKeyValueAdapter`.
- Stores values as `bytes` and supports optional TTL-based expiration using `time.monotonic()`.

## Public API
### Class: `PythonAdapter(IKeyValueAdapter)`
- `__init__() -> None`
  - Initializes an empty in-memory store and a lock.

- `get(key: str) -> bytes`
  - Returns the stored value.
  - Raises `KVNotFoundError` if the key is missing or expired.

- `set(key: str, value: bytes | str | memoryview, ttl: int | None = None) -> None`
  - Stores `value` (normalized to `bytes`) under `key`.
  - `ttl` (seconds) sets an expiration time; `None` means no expiration.

- `set_if_not_exists(key: str, value: bytes | str | memoryview, ttl: int | None = None) -> bool`
  - Stores only if the key does not exist (or has expired).
  - Returns `True` if inserted, `False` if the key already exists.

- `delete(key: str) -> None`
  - Deletes the key.
  - Raises `KVNotFoundError` if the key is missing or expired.

- `delete_if_value_matches(key: str, value: bytes | str | memoryview) -> bool`
  - Deletes the key only if it exists and its stored value equals the provided value (after normalization).
  - Returns `True` if deleted, otherwise `False`.

- `exists(key: str) -> bool`
  - Returns `True` if the key exists and is not expired; otherwise `False`.

## Configuration/Dependencies
- Depends on:
  - `naas_abi_core.services.keyvalue.KeyValuePorts.IKeyValueAdapter`
  - `naas_abi_core.services.keyvalue.KeyValuePorts.KVNotFoundError`
- Uses standard library:
  - `threading.Lock` for synchronization
  - `time.monotonic()` for TTL expiration

## Usage
```python
import time
from naas_abi_core.services.keyvalue.adapters.secondary.PythonAdapter import PythonAdapter
from naas_abi_core.services.keyvalue.KeyValuePorts import KVNotFoundError

kv = PythonAdapter()

kv.set("a", "hello", ttl=1)
print(kv.get("a"))  # b'hello'

time.sleep(1.1)
print(kv.exists("a"))  # False

try:
    kv.get("a")
except KVNotFoundError:
    print("expired")
```

## Caveats
- Storage is in-memory only; data is lost when the process stops.
- Expired keys are purged lazily (on access via `get`, `set_if_not_exists`, `delete`, `delete_if_value_matches`, `exists`), not by a background cleanup thread.
- TTL is interpreted as seconds and is based on `time.monotonic()` (not wall-clock time).
