# PythonAdapter

## What it is
- A key/value storage adapter implementing `IKeyValueAdapter`.
- Supports:
  - In-memory storage (default).
  - Optional SQLite-backed persistence with TTL (expiration) support.
- Thread-safe via a re-entrant lock (`threading.RLock`).

## Public API
### Class: `PythonAdapter(IKeyValueAdapter)`
#### `__init__(persistence_path: str | None = None, journal_mode: str = "WAL", busy_timeout_ms: int = 5000) -> None`
- Creates an adapter instance.
- If `persistence_path` is provided:
  - Opens/creates an SQLite DB file.
  - Ensures a `kv_store` table exists.
  - Applies SQLite pragmas: `journal_mode`, `synchronous=NORMAL`.

#### `get(key: str) -> bytes`
- Returns the stored value for `key` as `bytes`.
- Purges the key first if it is expired.
- Raises `KVNotFoundError` if missing (or expired and purged).

#### `set(key: str, value: bytes, ttl: int | None = None) -> None`
- Stores `value` under `key`.
- Optional `ttl` (seconds) sets an expiration timestamp.
- Value normalization:
  - `str` is encoded as UTF-8.
  - `memoryview` is converted to bytes.
  - otherwise coerced via `bytes(value)`.

#### `set_if_not_exists(key: str, value: bytes, ttl: int | None = None) -> bool`
- Stores `key` only if it does not already exist (after purging expiration).
- Returns:
  - `True` if inserted.
  - `False` if it already exists.

#### `delete(key: str) -> None`
- Deletes `key` (after purging expiration).
- Raises `KVNotFoundError` if missing.

#### `delete_if_value_matches(key: str, value: bytes) -> bool`
- Deletes `key` only if the stored value matches `value` (after normalization).
- Returns `True` if deleted, `False` otherwise (including key missing).

#### `exists(key: str) -> bool`
- Returns `True` if `key` exists (after purging expiration), else `False`.

## Configuration/Dependencies
- Dependencies:
  - Python stdlib: `sqlite3`, `threading`, `time`, `os`.
  - `naas_abi_core.services.keyvalue.KeyValuePorts`:
    - `IKeyValueAdapter`
    - `KVNotFoundError`
- SQLite persistence settings (when `persistence_path` is set):
  - `journal_mode` (default `"WAL"`)
  - `busy_timeout_ms` (default `5000` ms)
  - `check_same_thread=False` (connection used across threads; access is guarded by the adapter lock)

## Usage
### In-memory
```python
from naas_abi_core.services.keyvalue.adapters.secondary.PythonAdapter import PythonAdapter
from naas_abi_core.services.keyvalue.KeyValuePorts import KVNotFoundError

kv = PythonAdapter()
kv.set("greeting", "hello", ttl=10)

assert kv.exists("greeting")
print(kv.get("greeting").decode("utf-8"))

kv.delete("greeting")
try:
    kv.get("greeting")
except KVNotFoundError:
    print("missing")
```

### SQLite-backed persistence
```python
from naas_abi_core.services.keyvalue.adapters.secondary.PythonAdapter import PythonAdapter

kv = PythonAdapter(persistence_path="./data/kv.sqlite")
kv.set("k", b"v")
print(kv.get("k"))
```

## Caveats
- TTL expiration is enforced lazily:
  - Expired keys are purged only when operating on that key (`get`, `exists`, `set_if_not_exists`, `delete`, `delete_if_value_matches`).
  - No background cleanup of unrelated expired keys.
- SQLite mode:
  - Purging on expiration uses a `DELETE ... WHERE key = ? AND expires_at <= now`, but a non-expired row is still returned by `get` without checking `expires_at` in the `SELECT`. Expiration relies on the purge call happening first.
