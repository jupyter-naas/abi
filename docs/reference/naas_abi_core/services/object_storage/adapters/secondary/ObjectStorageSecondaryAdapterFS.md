# ObjectStorageSecondaryAdapterFS

## What it is
A filesystem-backed implementation of `IObjectStorageAdapter` that stores objects as files under a configured `base_path`, namespaced by `prefix` (directory) and `key` (filename).

## Public API
- **Class `ObjectStorageSecondaryAdapterFS(base_path: str)`**
  - `get_object(prefix: str, key: str) -> bytes`  
    Reads and returns the file contents for `base_path/prefix/key`.
  - `put_object(prefix: str, key: str, content: bytes) -> None`  
    Writes `content` to `base_path/prefix/key` using a temporary file + atomic replace.
  - `delete_object(prefix: str, key: str) -> None`  
    Deletes `base_path/prefix/key`.
  - `list_objects(prefix: str, queue: Optional[Queue] = None) -> list[str]`  
    Lists immediate entries in `base_path/prefix` and returns paths as `"{prefix}/{name}"`.  
    If `queue` is provided, each listed object is also `queue.put(...)`.
  - `get_object_metadata(prefix: str, key: str) -> ObjectMetaData`  
    Returns metadata for `base_path/prefix/key` including size, timestamps, permissions, and guessed MIME type/encoding.

### Errors
- Raises `Exceptions.ObjectNotFound` when the target `prefix` directory or `prefix/key` file does not exist.

## Configuration/Dependencies
- **Constructor argument**
  - `base_path`: Root directory under which all objects are stored.
- **Uses**
  - Standard library: `os`, `tempfile`, `threading`, `mimetypes`, `stat`, `datetime`, `queue.Queue`
  - `naas_abi_core.services.object_storage.ObjectStoragePort`:
    - `IObjectStorageAdapter`, `ObjectMetaData`, `Exceptions`

## Usage
```python
from naas_abi_core.services.object_storage.adapters.secondary.ObjectStorageSecondaryAdapterFS import (
    ObjectStorageSecondaryAdapterFS,
)

store = ObjectStorageSecondaryAdapterFS(base_path="/tmp/object-store")

store.put_object("images", "hello.txt", b"hello")
data = store.get_object("images", "hello.txt")
print(data.decode())  # "hello"

print(store.list_objects("images"))  # ["images/hello.txt"]

meta = store.get_object_metadata("images", "hello.txt")
print(meta.file_size_bytes, meta.mime_type)

store.delete_object("images", "hello.txt")
```

## Caveats
- `list_objects()` is non-recursive; it lists only direct entries under the `prefix` directory.
- `get_object_metadata()` does not acquire the instance lock (unlike other operations), so concurrent writes/deletes may affect results.
- Existence checks raise `Exceptions.ObjectNotFound` instead of returning `False`.
