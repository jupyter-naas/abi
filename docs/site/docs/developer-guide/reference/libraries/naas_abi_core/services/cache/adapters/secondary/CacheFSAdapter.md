# CacheFSAdapter

## What it is
- A filesystem-backed cache adapter implementing `ICacheAdapter`.
- Stores each cache entry as a JSON file in a directory; filenames are the SHA-256 hash of the cache key.
- Uses a process-local `threading.RLock` to serialize operations within the process.

## Public API
- `class CacheFSAdapter(ICacheAdapter)`
  - `__init__(cache_dir: str)`
    - Ensures `cache_dir` exists (`os.makedirs(..., exist_ok=True)`).
  - `get(key: str) -> CachedData`
    - Loads the JSON file for `key` and returns `CachedData(**data)`.
    - Raises `CacheNotFoundError` if the entry file does not exist.
  - `set(key: str, value: CachedData) -> None`
    - Writes/overwrites the cache entry (`value.model_dump()` as pretty JSON).
    - Uses a temp file in `cache_dir` and `os.replace()` for atomic replacement.
  - `set_if_absent(key: str, value: CachedData) -> bool`
    - Writes only if the entry does not already exist.
    - Returns `True` if created, `False` if already present.
  - `delete(key: str) -> None`
    - Removes the cache entry file.
    - Raises `CacheNotFoundError` if the entry file does not exist.
  - `exists(key: str) -> bool`
    - Returns whether the entry file exists.
  - `list_keys(prefix: str = "", *, limit: int = 100, after: str | None = None) -> CacheKeyPage`
    - Lists cached keys by scanning files in `cache_dir` whose names match a 64-hex SHA-256 pattern.
    - Reads each entry’s `"key"` field (optimizes by reading only the first 4096 bytes when possible).
    - Enforces page size via `check_page_limit(limit)` and paginates via `paginate_keys(...)`.

## Configuration/Dependencies
- Requires:
  - A writable `cache_dir` path.
  - Types and helpers from `naas_abi_core.services.cache.CachePort`:
    - `CachedData`, `CacheKeyPage`, `CacheNotFoundError`, `ICacheAdapter`, `check_page_limit`, `paginate_keys`.
- Storage format:
  - JSON: `json.dumps(value.model_dump(), indent=4)`
- File naming:
  - `sha256(key.encode()).hexdigest()`

## Usage
```python
from naas_abi_core.services.cache.adapters.secondary.CacheFSAdapter import CacheFSAdapter
from naas_abi_core.services.cache.CachePort import CachedData, CacheNotFoundError

cache = CacheFSAdapter(cache_dir=".cache")

key = "my-key"
value = CachedData(...)  # construct according to your CachedData model

cache.set(key, value)

if cache.exists(key):
    loaded = cache.get(key)

page = cache.list_keys(prefix="", limit=10)
print(page)

try:
    cache.delete(key)
except CacheNotFoundError:
    pass
```

## Caveats
- Concurrency:
  - Thread-safe within a single process (`RLock`), but no inter-process locking; multiple processes may race.
- `list_keys()` behavior:
  - Only considers files whose names look like SHA-256 hex strings; other files in `cache_dir` are ignored.
  - If an entry is deleted during listing, it is silently skipped (`FileNotFoundError` handled).
- Data at rest:
  - Values are stored as plaintext JSON in the filesystem.
