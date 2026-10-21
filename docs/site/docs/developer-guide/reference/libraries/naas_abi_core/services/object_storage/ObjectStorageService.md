# ObjectStorageService

## What it is
- A domain service that wraps an `IObjectStorageAdapter` to provide object storage operations.
- Normalizes `prefix` values by stripping a leading `"storage/"` (primarily for filesystem-backed adapters) before delegating to the adapter.

## Public API
### Class: `ObjectStorageService(adapter: IObjectStorageAdapter)`
- Purpose: Provide a stable object storage domain interface backed by a pluggable adapter.

#### Methods
- `get_object(prefix: str, key: str) -> bytes`
  - Fetch an object’s raw bytes via the adapter (after prefix normalization).
- `put_object(prefix: str, key: str, content: bytes) -> None`
  - Store object bytes via the adapter (after prefix normalization).
- `delete_object(prefix: str, key: str) -> None`
  - Delete an object via the adapter (after prefix normalization).
- `list_objects(prefix: str = "", queue: Optional[Queue] = None) -> list[str]`
  - List object keys via the adapter (after prefix normalization).
  - If `prefix == "/"`, it is converted to `""`.
  - Optionally accepts a `queue.Queue` to pass through to the adapter.
- `get_object_metadata(prefix: str, key: str) -> ObjectMetaData`
  - Return object metadata via the adapter.
  - Note: This method does **not** apply the `"storage/"` prefix normalization.

## Configuration/Dependencies
- Requires an implementation of `IObjectStorageAdapter` from `naas_abi_core.services.object_storage.ObjectStoragePort`.
- Uses:
  - `queue.Queue` (optional parameter for `list_objects`)
  - `ObjectMetaData` type for metadata returns
- Inherits from `ServiceBase` and implements `IObjectStorageDomain`.

## Usage
```python
from naas_abi_core.services.object_storage.ObjectStorageService import ObjectStorageService

# adapter must implement IObjectStorageAdapter
adapter = ...  # e.g., filesystem/S3 adapter provided elsewhere
svc = ObjectStorageService(adapter)

svc.put_object("storage/my-prefix", "hello.txt", b"hello")
data = svc.get_object("storage/my-prefix", "hello.txt")
keys = svc.list_objects("storage/my-prefix")
svc.delete_object("storage/my-prefix", "hello.txt")
```

## Caveats
- Prefix normalization (`"storage/"` removal and `"/"` → `""`) is applied to `get_object`, `put_object`, `delete_object`, and `list_objects`, but **not** to `get_object_metadata`. Ensure you pass the correct `prefix` format for metadata calls.
