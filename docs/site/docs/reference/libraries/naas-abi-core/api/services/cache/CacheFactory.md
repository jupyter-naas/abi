# CacheFactory

## What it is
- A small factory for creating a `CacheService` backed by a filesystem cache (`CacheFSAdapter`).
- Automatically locates (or creates) a `storage` directory and places the cache under a configurable subpath.

## Public API
- `class CacheFactory`
  - `@staticmethod CacheFS_find_storage(subpath: str = "cache", needle: str = "storage") -> CacheService`
    - Returns a `CacheService` configured with a `CacheFSAdapter` rooted at:
      - `<found_storage_folder>/<subpath>`
    - Ensures `subpath` is prefixed with `"cache"` (e.g., `"foo"` becomes `"cache/foo"`).
    - If no storage folder is found, creates `./storage` in the current working directory and retries.

## Configuration/Dependencies
- Depends on:
  - `naas_abi_core.services.cache.CacheService.CacheService`
  - `naas_abi_core.services.cache.adapters.secondary.CacheFSAdapter.CacheFSAdapter`
  - `naas_abi_core.utils.Storage.find_storage_folder`
  - `naas_abi_core.utils.Storage.NoStorageFolderFound`
- Filesystem behavior:
  - Uses `os.getcwd()` as the starting point for locating the storage folder.
  - Creates `os.path.join(os.getcwd(), "storage")` if a storage folder is not found.

## Usage
```python
from naas_abi_core.services.cache.CacheFactory import CacheFactory

cache = CacheFactory.CacheFS_find_storage()              # uses subpath "cache"
cache2 = CacheFactory.CacheFS_find_storage("myapp")      # uses subpath "cache/myapp"
```

## Caveats
- If no storage folder is found, this will create a `storage/` directory in the current working directory.
