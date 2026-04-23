# ObjectStorageSecondaryAdapterFS

## What it is
- A filesystem-backed implementation of `IObjectStorageAdapter`.
- Stores objects as files under a configurable `base_path`, grouped by `prefix` (directory).

## Public API
- **Class: `ObjectStorageSecondaryAdapterFS(base_path: str)`**
  - Initializes the adapter and ensures the base directory exists.

- **Methods (from `IObjectStorageAdapter`):**
  - `get_object(prefix: str, key: str) -> bytes`
    - Reads and returns the object content from `base_path/prefix/key`.
    - Raises `Exceptions.ObjectNotFound` if the file does not exist.
  - `put_object(prefix: str, key: str, content: bytes) -> None`
    - Ensures the `prefix` directory exists and writes `content` to `base_path/prefix/key`.
  - `delete_object(prefix: str, key: str) -> None`
    - Deletes `base_path/prefix/key`.
    - Raises `Exceptions.ObjectNotFound` if the file does not exist.
  - `list_objects(prefix: str, queue: Optional[Queue] = None) -> list[str]`
    - Lists entries in `base_path/prefix` and returns paths as `os.path.join(prefix, filename)`.
    - Raises `Exceptions.ObjectNotFound` if the prefix directory does not exist.
    - Note: `queue` parameter is accepted but not used.

## Configuration/Dependencies
- **Dependencies:**
  - Standard library: `os`, `queue.Queue`, `typing.Optional`
  - `naas_abi_core.services.object_storage.ObjectStoragePort`:
    - `IObjectStorageAdapter`
    - `Exceptions` (uses `Exceptions.ObjectNotFound`)

- **Configuration:**
  - `base_path`: root directory where all object data is stored.

## Usage
```python
from naas_abi_core.services.object_storage.adapters.secondary.ObjectStorageSecondaryAdapterFS import (
    ObjectStorageSecondaryAdapterFS
)

store = ObjectStorageSecondaryAdapterFS(base_path="/tmp/object_store")

store.put_object("images", "cat.jpg", b"binary-data")
data = store.get_object("images", "cat.jpg")

keys = store.list_objects("images")  # e.g. ["images/cat.jpg"]
store.delete_object("images", "cat.jpg")
```

## Caveats
- `list_objects()` returns all directory entries from `os.listdir()` (no filtering for files vs subdirectories).
- `queue` argument in `list_objects()` is unused.
- Paths are built via `os.path.join`; callers should treat `prefix`/`key` as relative identifiers to avoid unintended path traversal.
