# ObjectStorageService

## What it is
- A thin domain service wrapping an `IObjectStorageAdapter`.
- Normalizes object prefixes by stripping a leading `storage/` to avoid creating an extra `storage` folder (notably with filesystem-backed adapters).

## Public API

### Class: `ObjectStorageService(adapter: IObjectStorageAdapter)`
Implements `IObjectStorageDomain` and delegates operations to the provided adapter.

#### Methods
- `get_object(prefix: str, key: str) -> bytes`
  - Returns object content for `prefix`/`key` via the adapter after prefix normalization.
- `put_object(prefix: str, key: str, content: bytes) -> None`
  - Stores `content` at `prefix`/`key` via the adapter after prefix normalization.
- `delete_object(prefix: str, key: str) -> None`
  - Deletes `prefix`/`key` via the adapter after prefix normalization.
- `list_objects(prefix: str = "", queue: Optional[Queue] = None) -> list[str]`
  - Lists objects under `prefix` via the adapter after prefix normalization.
  - Special case: if normalized `prefix == "/"`, it is converted to `""` before delegation.

## Configuration/Dependencies
- Requires an implementation of `IObjectStorageAdapter` (from `naas_abi_core.services.object_storage.ObjectStoragePort`).
- Optional dependency for `list_objects`: a `queue.Queue` instance passed through to the adapter.

## Usage
```python
from naas_abi_core.services.object_storage.ObjectStorageService import ObjectStorageService

# adapter must implement IObjectStorageAdapter (not shown here)
adapter = ...  # e.g., filesystem/S3 adapter implementation

svc = ObjectStorageService(adapter)

svc.put_object("storage/my-prefix", "hello.txt", b"hello")
data = svc.get_object("storage/my-prefix", "hello.txt")
keys = svc.list_objects("storage/my-prefix")
svc.delete_object("storage/my-prefix", "hello.txt")
```

## Caveats
- Prefix normalization only removes a leading `"storage/"`. Other occurrences are not altered.
- `list_objects()` treats `"/"` as the empty prefix (`""`).
