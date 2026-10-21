# PythonAdapter

## What it is
- A key/value storage adapter implementing `IKeyValueAdapter`.
- Supports:
  - In-memory storage (default).
  - Optional SQLite-backed persistence with TTL (expiration) support.
- Thread-safe via a re-entrant lock (`threading.RLock`).

## Public API

### Class: `PythonAdapter(IKeyValueAdapter)`
Key/value operations with optional persistence.

- `__init__(persistence_path: str | None = None, journal_mode: str = "WAL", busy_timeout_ms: int = 5000) -> None`
  - Creates an adapter instance.
  - If `persistence_path` is provided:
    - Creates parent directory if needed.
    - Opens/creates an SQLite DB file and initializes table `kv_store(key, value, expires_at)`.
    - Applies pragmas: `journal_mode`, `busy_timeout`, `synchronous=NORMAL`.
    - Uses `check_same_thread=False` (adapter serializes access via its lock).

- `get(key: str) -> bytes`
  - Returns the stored value for `key` as `bytes`.
  - Purges the key first if it is expired.
  - Raises `KVNotFoundError` if missing (or expired and purged).

- `set(key: str, value: bytes, ttl: int | None = None) -> None`
  - Stores `value` under `key` (insert/replace).
  - Optional `ttl` (seconds) sets an absolute expiration timestamp.
  - Normalizes value:
    - `str` → UTF-8 bytes
    - `memoryview` → `.tobytes()`
    - otherwise `bytes(value)`

- `set_if_not_exists(key: str, value: bytes, ttl: int | None = None) -> bool`
  - Stores `key` only if it does not already exist (after purging expiration).
  - Returns:
    - `True` if inserted
    - `False` if it already exists

- `delete(key: str) -> None`
  - Deletes `key` (after purging expiration).
  - Raises `KVNotFoundError` if missing.

- `delete_if_value_matches(key: str, value: bytes) -> bool`
  - Deletes `key` only if the stored value matches the provided value (after normalization and expiration purge).
  - Returns `True` if deleted, `False` otherwise (including key missing).

- `exists(key: str) -> bool`
  - Returns `True` if `key` exists (after purging expiration), else `False`.

- `list_keys(prefix: str = "", *, limit: int = 100, after: str | None = None) -> KVKeyPage`
  - Lists non-expired keys filtered by `prefix`, ordered lexicographically.
  - Pagination:
    - `limit` is validated via `check_page_limit(limit)`.
    - `after` is an exclusive cursor (`key > after`).
  - Returns `KVKeyPage(keys, next_after)` where `next_after` is the last key of the returned page when more results exist.

- `get_ttl(key: str) -> int | None`
  - Returns remaining TTL in seconds (rounded up), with a minimum of `1` when expiring in less than one second.
  - Returns `None` if the key exists and has no expiration.
  - Raises `KVNotFoundError` if missing (or expired and purged).

## Configuration/Dependencies
- Stdlib dependencies: `math`, `os`, `sqlite3`, `threading`, `time`, `dataclasses`.
- `naas_abi_core.services.keyvalue.KeyValuePorts`:
  - `IKeyValueAdapter`, `KVKeyPage`, `KVNotFoundError`, `check_page_limit`, `paginate_keys`
- SQLite options (when `persistence_path` is set):
  - `journal_mode` (default `"WAL"`)
  - `busy_timeout_ms` (default `5000` ms)

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
  - Expired keys are purged only when operating on that specific key (`get`, `exists`, `set_if_not_exists`, `delete`, `delete_if_value_matches`, `get_ttl`).
  - `list_keys` filters out expired entries by checking timestamps but does not delete them.
- SQLite mode commits after purge/delete/write operations to avoid holding a write lock longer than necessary.
