# CacheObjectStorageAdapter

## What it is
- An `ICacheAdapter` implementation that persists cache entries in an object storage backend.
- Entries are stored as JSON objects under `<prefix>/entries/` with filenames derived from `sha256(cache_key)`.
- Supports basic CRUD plus key listing via full scan of stored entries.

## Public API
- **Class: `CacheObjectStorageAdapter(object_storage: ObjectStorageService, prefix: str = "cache")`**
  - Creates an adapter backed by `ObjectStorageService`.
  - Normalizes `prefix` by stripping leading/trailing `/`.

- **Method: `get(key: str) -> CachedData`**
  - Reads and returns the cached entry for `key`.
  - Raises `CacheNotFoundError` if the object is missing.

- **Method: `set(key: str, value: CachedData) -> None`**
  - Serializes `value.model_dump()` to JSON and stores it at the hashed object key.

- **Method: `set_if_absent(key: str, value: CachedData) -> bool`**
  - Best-effort conditional write:
    - Returns `False` if `exists(key)` is `True`.
    - Otherwise writes and returns `True`.
  - Not atomic under concurrency (check-then-act).

- **Method: `delete(key: str) -> None`**
  - Deletes the stored entry for `key`.
  - Raises `CacheNotFoundError` if the object is missing.

- **Method: `exists(key: str) -> bool`**
  - Returns `True` if the backing object can be read; otherwise `False`.

- **Method: `list_keys(prefix: str = "", *, limit: int = 100, after: str | None = None) -> CacheKeyPage`**
  - Lists cached keys by:
    - Listing objects under `<prefix>/entries/`,
    - Filtering filenames matching `[0-9a-f]{64}.json`,
    - Reading each entry and extracting the `"key"` field from its JSON payload.
  - Applies pagination/filtering via `paginate_keys(...)` and enforces limits via `check_page_limit(limit)`.

## Configuration/Dependencies
- **Depends on**:
  - `naas_abi_core.services.object_storage.ObjectStorageService.ObjectStorageService`
    - Used methods: `get_object(prefix, key)`, `put_object(prefix, key, payload)`, `delete_object(prefix, key)`, `list_objects(prefix)`.
  - `naas_abi_core.services.object_storage.ObjectStoragePort.Exceptions`
    - Catches `Exceptions.ObjectNotFound`.
  - `naas_abi_core.services.cache.CachePort`
    - Types/utilities: `CachedData`, `CacheKeyPage`, `CacheNotFoundError`, `ICacheAdapter`, `check_page_limit`, `paginate_keys`.

- **Storage layout**
  - Entry prefix: `PurePosixPath(prefix, "entries").as_posix()`
  - Entry filename: `sha256(key) + ".json"`

## Usage
```python
from naas_abi_core.services.cache.adapters.secondary.CacheObjectStorageAdapter import (
    CacheObjectStorageAdapter,
)
from naas_abi_core.services.cache.CachePort import CachedData
from naas_abi_core.services.object_storage.ObjectStorageService import ObjectStorageService

object_storage = ObjectStorageService(...)  # provide a configured concrete service
cache = CacheObjectStorageAdapter(object_storage, prefix="cache")

value = CachedData(...)  # construct per your CachedData model
cache.set("my-key", value)

loaded = cache.get("my-key")
assert cache.exists("my-key") is True

page = cache.list_keys(prefix="my-", limit=50)
cache.delete("my-key")
```

## Caveats
- `set_if_absent` is **not atomic**; concurrent writers may race (check-then-write).
- `exists()` performs a full `get_object` read to determine presence.
- `list_keys()` is **O(number of entries)** and reads each entry object to extract the stored `"key"` field; it may be expensive for large caches.
