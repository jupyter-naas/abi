# ObjectStoragePort

## What it is
Defines abstract interfaces (ports) for an object storage service:
- **Adapter port** for infrastructure implementations (e.g., S3, filesystem).
- **Domain port** for application/domain layer usage.
Also defines storage-related exception types.

## Public API

### `Exceptions`
Container for exception types:
- `Exceptions.ObjectNotFound`: Raised when an object cannot be found.
- `Exceptions.ObjectAlreadyExists`: Raised when attempting to create an object that already exists.

### `IObjectStorageAdapter` (abstract base class)
Interface to be implemented by object storage adapters.

Methods:
- `get_object(prefix: str, key: str) -> bytes`: Retrieve object content.
- `put_object(prefix: str, key: str, content: bytes) -> None`: Store object content.
- `delete_object(prefix: str, key: str) -> None`: Delete an object.
- `list_objects(prefix: str, queue: Optional[Queue] = None) -> list[str]`: List object keys under a prefix; may optionally use a `Queue`.

### `IObjectStorageDomain` (abstract base class)
Interface for the domain/application layer; mirrors the adapter API.

Methods:
- `get_object(prefix: str, key: str) -> bytes`
- `put_object(prefix: str, key: str, content: bytes) -> None`
- `delete_object(prefix: str, key: str) -> None`
- `list_objects(prefix: str, queue: Optional[Queue] = None) -> list[str]`

## Configuration/Dependencies
- Python standard library:
  - `abc.ABC`, `abc.abstractmethod`
  - `queue.Queue`
  - `typing.Optional`

No runtime configuration is defined in this module.

## Usage
Implement one of the interfaces and use it through the abstract type.

```python
from queue import Queue
from naas_abi_core.services.object_storage.ObjectStoragePort import (
    IObjectStorageAdapter, Exceptions
)

class InMemoryObjectStorage(IObjectStorageAdapter):
    def __init__(self):
        self._store = {}

    def get_object(self, prefix: str, key: str) -> bytes:
        k = (prefix, key)
        if k not in self._store:
            raise Exceptions.ObjectNotFound()
        return self._store[k]

    def put_object(self, prefix: str, key: str, content: bytes) -> None:
        self._store[(prefix, key)] = content

    def delete_object(self, prefix: str, key: str) -> None:
        self._store.pop((prefix, key), None)

    def list_objects(self, prefix: str, queue: Queue | None = None) -> list[str]:
        keys = [k for (p, k) in self._store.keys() if p == prefix]
        if queue is not None:
            for k in keys:
                queue.put(k)
        return keys

storage = InMemoryObjectStorage()
storage.put_object("docs", "readme.txt", b"hello")
print(storage.get_object("docs", "readme.txt"))
print(storage.list_objects("docs"))
```

## Caveats
- These are **interfaces only**; no concrete storage behavior is provided.
- `list_objects(..., queue=...)` accepts an optional `Queue`, but how/if it is used is implementation-defined.
