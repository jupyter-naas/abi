# CacheObjectStorageAdapter

## What it is
- An `ICacheAdapter` implementation that stores cache entries in an object storage backend.
- Cache keys are hashed (SHA-256) and stored as JSON files under a configurable prefix.

## Public API
- **Class: `CacheObjectStorageAdapter(object_storage: ObjectStorageService, prefix: str = "cache")`**
  - Creates a cache adapter using the provided `ObjectStorageService`.
  - `prefix` is normalized by stripping leading/trailing `/`.

- **Method: `get(key: str) -> CachedData`**
  - Fetches and returns the cached entry for `key`.
  - Raises `CacheNotFoundError` if not present.

- **Method: `set(key: str, value: CachedData) -> None`**
  - Writes `value` to object storage as JSON.

- **Method: `set_if_absent(key: str, value: CachedData) -> bool`**
  - Best-effort conditional write:
    - Returns `False` if the entry already exists at check time.
    - Otherwise writes and returns `True`.
  - Not atomic under concurrency.

- **Method: `delete(key: str) -> None`**
  - Deletes the cached entry.
  - Raises `CacheNotFoundError` if not present.

- **Method: `exists(key: str) -> bool`**
  - Returns `True` if the entry exists, else `False`.

## Configuration/Dependencies
- Depends on:
  - `naas_abi_core.services.object_storage.ObjectStorageService.ObjectStorageService`
    - Must provide: `get_object(prefix, key)`, `put_object(prefix, key, payload)`, `delete_object(prefix, key)`.
  - `naas_abi_core.services.cache.CachePort`
    - `CachedData` (must support `model_dump()` and construction via `CachedData(**dict)`).
    - `CacheNotFoundError`.
- Storage layout:
  - Objects are stored under `<prefix>/entries/`.
  - Filename is `sha256(key) + ".json"`.

## Usage
```python
from naas_abi_core.services.cache.adapters.secondary.CacheObjectStorageAdapter import (
    CacheObjectStorageAdapter,
)
from naas_abi_core.services.cache.CachePort import CachedData
from naas_abi_core.services.object_storage.ObjectStorageService import ObjectStorageService

object_storage = ObjectStorageService(...)  # provide a concrete, configured service
cache = CacheObjectStorageAdapter(object_storage, prefix="cache")

data = CachedData(...)  # construct according to your CachedData model
cache.set("my-key", data)

loaded = cache.get("my-key")
assert cache.exists("my-key") is True

wrote = cache.set_if_absent("my-key", data)  # likely False after initial set
cache.delete("my-key")
```

## Caveats
- `set_if_absent` is **not atomic** and is subject to check-then-act races under concurrent callers.
- Cache keys are **not stored verbatim**; they are hashed to a SHA-256 filename, so the original key cannot be derived from storage paths.
- `exists()` performs a read (`get_object`) to determine existence, which may be more expensive than a metadata/head call if your object storage supports one.
