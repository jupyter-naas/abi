# ObjectStoragePort

## What it is
- A small “port” module defining:
  - Exceptions for object storage operations.
  - A Pydantic model describing object metadata.
  - Two abstract interfaces (ABCs) for object storage adapters and domain services.

## Public API

### `Exceptions`
- `Exceptions.ObjectNotFound(Exception)`: Raised when a requested object does not exist.
- `Exceptions.ObjectAlreadyExists(Exception)`: Raised when attempting to create an object that already exists.

### `ObjectMetaData` (`pydantic.BaseModel`)
Represents metadata for an object:
- `file_path: str`
- `file_name: str`
- `file_size_bytes: int`
- `created_time: Optional[datetime]`
- `modified_time: Optional[datetime]`
- `accessed_time: Optional[datetime]`
- `permissions: Optional[str]`
- `mime_type: Optional[str]`
- `encoding: Optional[str]`

### `IObjectStorageAdapter` (`abc.ABC`)
Abstract interface typically implemented by infrastructure/storage backends.
- `get_object(prefix: str, key: str) -> bytes`: Fetch object content.
- `put_object(prefix: str, key: str, content: bytes) -> None`: Store object content.
- `delete_object(prefix: str, key: str) -> None`: Remove an object.
- `list_objects(prefix: str, queue: Optional[Queue] = None) -> list[str]`: List object keys under a prefix (optionally uses a `Queue`).
- `get_object_metadata(prefix: str, key: str) -> ObjectMetaData`: Fetch metadata for an object.

### `IObjectStorageDomain` (`abc.ABC`)
Abstract interface for a domain/service layer with the same contract as the adapter.
- `get_object(prefix: str, key: str) -> bytes`
- `put_object(prefix: str, key: str, content: bytes) -> None`
- `delete_object(prefix: str, key: str) -> None`
- `list_objects(prefix: str, queue: Optional[Queue] = None) -> list[str]`
- `get_object_metadata(prefix: str, key: str) -> ObjectMetaData`

## Configuration/Dependencies
- Python standard library:
  - `abc` (for abstract base classes)
  - `datetime.datetime`
  - `queue.Queue`
  - `typing.Optional`
- Third-party:
  - `pydantic.BaseModel` (for `ObjectMetaData`)

## Usage

```python
from datetime import datetime
from queue import Queue

from naas_abi_core.services.object_storage.ObjectStoragePort import (
    IObjectStorageAdapter,
    ObjectMetaData,
)

class InMemoryObjectStorage(IObjectStorageAdapter):
    def __init__(self):
        self._store: dict[tuple[str, str], bytes] = {}

    def get_object(self, prefix: str, key: str) -> bytes:
        return self._store[(prefix, key)]

    def put_object(self, prefix: str, key: str, content: bytes) -> None:
        self._store[(prefix, key)] = content

    def delete_object(self, prefix: str, key: str) -> None:
        del self._store[(prefix, key)]

    def list_objects(self, prefix: str, queue: Queue | None = None) -> list[str]:
        keys = [k for (p, k) in self._store.keys() if p == prefix]
        if queue is not None:
            for k in keys:
                queue.put(k)
        return keys

    def get_object_metadata(self, prefix: str, key: str) -> ObjectMetaData:
        content = self._store[(prefix, key)]
        return ObjectMetaData(
            file_path=f"{prefix}/{key}",
            file_name=key,
            file_size_bytes=len(content),
            created_time=datetime.utcnow(),
            modified_time=None,
            accessed_time=None,
            permissions=None,
            mime_type=None,
            encoding=None,
        )

storage = InMemoryObjectStorage()
storage.put_object("docs", "readme.txt", b"hello")
print(storage.get_object("docs", "readme.txt"))
print(storage.list_objects("docs"))
print(storage.get_object_metadata("docs", "readme.txt").file_size_bytes)
```

## Caveats
- This module defines interfaces only; concrete behavior (including when `ObjectNotFound`/`ObjectAlreadyExists` are raised) depends on implementations.
- `list_objects(..., queue=...)` includes an optional `Queue`, but the interface does not specify how it must be used beyond being passed in.
