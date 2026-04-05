# CacheFSAdapter

## What it is
- A filesystem-backed cache adapter implementing `ICacheAdapter`.
- Stores each cache entry as a JSON file under a configured directory.
- Uses SHA-256 of the cache key as the filename.

## Public API
- `class CacheFSAdapter(ICacheAdapter)`
  - `__init__(cache_dir: str)`
    - Ensures `cache_dir` exists (creates it if missing).
  - `get(key: str) -> CachedData`
    - Loads and returns cached data from the corresponding JSON file.
    - Raises `CacheNotFoundError` if the cache file does not exist.
  - `set(key: str, value: CachedData) -> None`
    - Writes `value` as JSON to the file derived from `key`.
  - `delete(key: str) -> None`
    - Deletes the cache file derived from `key`.
    - Raises `CacheNotFoundError` if the cache file does not exist.
  - `exists(key: str) -> bool`
    - Returns `True` if the cache file for `key` exists, else `False`.

## Configuration/Dependencies
- Inputs:
  - `cache_dir`: directory path used to store cache files.
- Depends on:
  - `naas_abi_core.services.cache.CachePort`:
    - `CachedData` (data model; must support `CachedData(**dict)` and `model_dump()`),
    - `CacheNotFoundError`,
    - `ICacheAdapter`.

## Usage
```python
from naas_abi_core.services.cache.adapters.secondary.CacheFSAdapter import CacheFSAdapter
from naas_abi_core.services.cache.CachePort import CachedData, CacheNotFoundError

cache = CacheFSAdapter(cache_dir=".cache")

key = "my-cache-key"
value = CachedData()  # populate fields as required by your CachedData model

cache.set(key, value)

if cache.exists(key):
    loaded = cache.get(key)
    print(loaded)

try:
    cache.delete(key)
except CacheNotFoundError:
    pass
```

## Caveats
- Cache filenames are SHA-256 hashes of keys; original keys are not used as filenames.
- `get()`/`delete()` raise `CacheNotFoundError` when the corresponding file is missing.
- Stored format is JSON generated from `CachedData.model_dump()`; loading expects JSON to match `CachedData(**data)`.
