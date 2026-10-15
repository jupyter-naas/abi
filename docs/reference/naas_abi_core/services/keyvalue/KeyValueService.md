# KeyValueService

## What it is
- A service wrapper around an `IKeyValueAdapter` providing key/value operations.
- Adds optional event publishing (`KeyValueSet`, `KeyValueDeleted`, `KeyValueError`) when services are wired and an events service is available.
- Provides a simple distributed-style lock using `set_if_not_exists` + `delete_if_value_matches`.

## Public API

### Class: `KeyValueService`
- `__init__(adapter: IKeyValueAdapter)`
  - Stores the adapter and initializes `ServiceBase`.

- `adapter -> IKeyValueAdapter` (property)
  - Exposes the wrapped adapter (e.g., for adapter-type checks).

- `get(key: str) -> bytes`
  - Returns the raw value for `key` from the adapter.

- `set(key: str, value: bytes, ttl: int | None = None) -> None`
  - Delegates to adapter.
  - On adapter exception: publishes `KeyValueError(operation="set")` then re-raises.
  - On success: publishes `KeyValueSet(size_bytes=len(value), ttl_seconds=ttl)`.

- `set_if_not_exists(key: str, value: bytes, ttl: int | None = None) -> bool`
  - Delegates to adapter; returns whether the key was written.
  - On adapter exception: publishes `KeyValueError(operation="set_if_not_exists")` then re-raises.
  - On success and wrote: publishes `KeyValueSet(...)`.

- `delete(key: str) -> None`
  - Delegates to adapter.
  - On adapter exception: publishes `KeyValueError(operation="delete")` then re-raises.
  - On success: publishes `KeyValueDeleted`.

- `delete_if_value_matches(key: str, value: bytes) -> bool`
  - Delegates to adapter; returns whether deletion occurred.
  - On adapter exception: publishes `KeyValueError(operation="delete_if_value_matches")` then re-raises.
  - On success and deleted: publishes `KeyValueDeleted`.

- `exists(key: str) -> bool`
  - Returns whether `key` exists (adapter-defined semantics).

- `list_keys(prefix: str = "", *, limit: int = 100, after: str | None = None) -> KVKeyPage`
  - Returns a page of keys in ascending order (adapter-defined).
  - Validates `limit` via `check_page_limit(limit)`.
  - Use `page.next_after` as the next `after` cursor.

- `get_ttl(key: str) -> int | None`
  - Returns seconds before `key` expires, or `None` if it never expires (adapter-defined).
  - Docstring notes: raises `KVNotFoundError` (defined/raised by adapter).

- `lock(key: str, *, ttl: int = 30, timeout: float = 10.0, retry_delay: float = 0.05) -> context manager`
  - Context manager that attempts to acquire an exclusive lock on `key`.
  - Acquire: `set_if_not_exists(key, token, ttl=ttl)` with a random token.
  - Release (in `finally`): `delete_if_value_matches(key, token)`.
  - Retry: exponential backoff (capped) with small jitter until `timeout`.
  - Raises `ValueError` if `ttl <= 0`, `timeout < 0`, or `retry_delay < 0`.
  - Raises `KVLockTimeoutError(key, attempts, timeout)` if not acquired.

## Configuration/Dependencies
- Depends on:
  - `IKeyValueAdapter` and its methods:
    - `get`, `set`, `set_if_not_exists`, `delete`, `delete_if_value_matches`, `exists`, `list_keys`, `get_ttl`
  - Pagination types/utilities: `KVKeyPage`, `check_page_limit`
  - Lock error: `KVLockTimeoutError`
  - Base class: `ServiceBase` (for `services_wired` and `services.events` access)
  - Event ontology objects: `KeyValueSet`, `KeyValueDeleted`, `KeyValueError`
- Event publishing behavior:
  - Only attempts to publish when `self.services_wired` is true **and** `self.services.events_available()` returns true.
  - Publish failures are logged and do not affect KV operations.

## Usage

```python
from naas_abi_core.services.keyvalue.KeyValueService import KeyValueService
from naas_abi_core.services.keyvalue.KeyValuePorts import IKeyValueAdapter

class InMemoryAdapter(IKeyValueAdapter):
    def __init__(self): self.store = {}
    def get(self, key: str) -> bytes: return self.store[key]
    def set(self, key: str, value: bytes, ttl=None) -> None: self.store[key] = value
    def set_if_not_exists(self, key: str, value: bytes, ttl=None) -> bool:
        if key in self.store: return False
        self.store[key] = value; return True
    def delete(self, key: str) -> None: self.store.pop(key, None)
    def delete_if_value_matches(self, key: str, value: bytes) -> bool:
        if self.store.get(key) == value:
            del self.store[key]; return True
        return False
    def exists(self, key: str) -> bool: return key in self.store
    def list_keys(self, prefix: str, limit: int = 100, after: str | None = None):
        raise NotImplementedError
    def get_ttl(self, key: str): raise NotImplementedError

kv = KeyValueService(InMemoryAdapter())

kv.set("k", b"v", ttl=60)
assert kv.get("k") == b"v"

with kv.lock("lock:critical", ttl=5, timeout=1.0):
    kv.set("inside", b"ok")
```

## Caveats
- TTL support, missing-key behavior, and atomicity/concurrency guarantees are adapter-defined.
- The `lock()` mechanism is only as reliable/atomic as the adapter implementation; ensure `ttl` exceeds the critical section duration.
- Events are best-effort: publishing failures are swallowed (logged) and never block KV operations.
