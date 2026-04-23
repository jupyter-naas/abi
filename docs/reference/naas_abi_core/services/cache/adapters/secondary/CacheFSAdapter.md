# CacheFSAdapter

## What it is
- A filesystem-backed cache adapter implementing `ICacheAdapter`.
- Stores each cache entry as a JSON file in a given directory, named by the SHA-256 hash of the cache key.
- Uses a re-entrant lock (`threading.RLock`) to serialize operations within a process.

## Public API
- `class CacheFSAdapter(ICacheAdapter)`
  - `__init__(cache_dir: str)`
    - Ensures `cache_dir` exists (creates it if missing).
  - `get(key: str) -> CachedData`
    - Reads the JSON cache file for `key` and returns a `CachedData`.
    - Raises `CacheNotFoundError` if the entry does not exist.
  - `set(key: str, value: CachedData) -> None`
    - Writes/overwrites the cache entry for `key`.
    - Uses a temporary file and `os.replace()` for atomic replacement.
  - `set_if_absent(key: str, value: CachedData) -> bool`
    - Writes the cache entry only if it does not already exist.
    - Returns `True` if written, `False` if already present.
  - `delete(key: str) -> None`
    - Deletes the cache entry for `key`.
    - Raises `CacheNotFoundError` if the entry does not exist.
  - `exists(key: str) -> bool`
    - Returns `True` if the cache entry exists, else `False`.

## Configuration/Dependencies
- Requires:
  - `cache_dir`: directory where cache files are stored.
  - `CachedData`, `CacheNotFoundError`, `ICacheAdapter` from `naas_abi_core.services.cache.CachePort`.
- Storage format:
  - JSON (`value.model_dump()`), pretty-printed with `indent=4`.
- File naming:
  - `sha256(key.encode()).hexdigest()`.

## Usage
```python
from naas_abi_core.services.cache.adapters.secondary.CacheFSAdapter import CacheFSAdapter
from naas_abi_core.services.cache.CachePort import CachedData, CacheNotFoundError

cache = CacheFSAdapter(cache_dir=".cache")

key = "my-key"
value = CachedData(...)  # fill required fields for your CachedData model

cache.set(key, value)

if cache.exists(key):
    loaded = cache.get(key)

try:
    cache.delete(key)
except CacheNotFoundError:
    pass
```

## Caveats
- Concurrency:
  - Thread-safe within a single process via `RLock`.
  - No inter-process locking; concurrent writers from multiple processes may race.
- Key privacy/traceability:
  - Filenames are hashes of keys (keys not stored as filenames), but values are stored in plaintext JSON.
- Error behavior:
  - `get()` and `delete()` raise `CacheNotFoundError` when the entry file is missing.
