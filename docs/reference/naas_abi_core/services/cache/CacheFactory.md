# CacheFactory

## What it is
- A small factory module that builds `CacheService` instances backed by:
  - a filesystem cache under a `storage/.../cache` path, or
  - an object storage backend via `ObjectStorageService`.

## Public API
- `class CacheFactory`
  - `CacheFS_find_storage(subpath: str = "cache", needle: str = "storage") -> CacheService`
    - Creates a `CacheService` configured with a single cold-tier (`TIER_COLD`) `CacheFSAdapter`.
    - Locates (or creates) a `storage` folder relative to the current working directory, then appends `subpath` under a `cache` root.
  - `CacheObjectStorage(object_storage: ObjectStorageService, cache_prefix: str = "cache") -> CacheService`
    - Creates a `CacheService` configured with a single cold-tier (`TIER_COLD`) `CacheObjectStorageAdapter`.
    - Uses `cache_prefix` as the key prefix in the object storage backend.

## Configuration/Dependencies
- Depends on:
  - `CacheService` and `TIER_COLD`
  - `CacheFSAdapter`
  - `CacheObjectStorageAdapter`
  - `ObjectStorageService`
  - `find_storage_folder` and `NoStorageFolderFound`
- Filesystem variant behavior:
  - Uses `os.getcwd()` as the starting point for `find_storage_folder(...)`.
  - If no storage folder is found, creates `./storage` and retries.

## Usage
```python
from naas_abi_core.services.cache.CacheFactory import CacheFactory

# Filesystem-backed cache (auto-finds or creates ./storage, then uses storage/.../cache)
cache = CacheFactory.CacheFS_find_storage()

# Optional subpath (will be placed under "cache/<subpath>" unless it already starts with "cache")
cache2 = CacheFactory.CacheFS_find_storage(subpath="my_app")
```

```python
from naas_abi_core.services.cache.CacheFactory import CacheFactory
from naas_abi_core.services.object_storage.ObjectStorageService import ObjectStorageService

# Object storage-backed cache
object_storage = ObjectStorageService(...)  # construct per your environment
cache = CacheFactory.CacheObjectStorage(object_storage, cache_prefix="cache")
```

## Caveats
- `CacheFS_find_storage` will create a `storage` directory in the current working directory if no storage folder is found by `find_storage_folder(...)`.
- `subpath` is forced under a `cache` root unless it already starts with `"cache"`.
