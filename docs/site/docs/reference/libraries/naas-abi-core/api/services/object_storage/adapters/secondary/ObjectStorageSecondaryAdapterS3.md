# ObjectStorageSecondaryAdapterS3

## What it is
- A secondary adapter implementing `IObjectStorageAdapter` backed by Amazon S3 (or S3-compatible) using `boto3`.
- Supports basic object operations in a bucket, optionally scoped under a `base_prefix`.

## Public API
### Class: `ObjectStorageSecondaryAdapterS3(IObjectStorageAdapter)`
- `__init__(bucket_name, access_key_id, secret_access_key, base_prefix="", session_token=None, endpoint_url=None)`
  - Creates a `boto3` S3 client with the provided credentials.
  - If `endpoint_url` is provided, uses it (useful for S3-compatible storage).

- `get_object(prefix: str, key: str) -> bytes`
  - Downloads an object and returns its content as bytes.
  - Raises `Exceptions.ObjectNotFound` if the object does not exist.

- `put_object(prefix: str, key: str, content: bytes) -> None`
  - Uploads bytes to `s3://{bucket}/{base_prefix}/{prefix}/{key}`.

- `delete_object(prefix: str, key: str) -> None`
  - Deletes an object.
  - Raises `Exceptions.ObjectNotFound` if the object does not exist.

- `list_objects(prefix: str, queue: Optional[Queue] = None) -> list[str]`
  - Lists direct children (depth 1) under the given `prefix` using `Delimiter="/"`.
  - Returns a list of keys/prefixes with `base_prefix` stripped from returned entries.
  - If `queue` is provided, each entry is also `queue.put(...)`-ed.
  - Raises `Exceptions.ObjectNotFound` if the prefix has no objects.

## Configuration/Dependencies
- Dependencies:
  - `boto3`
  - `botocore.exceptions.ClientError`
  - `naas_abi_core.services.object_storage.ObjectStoragePort`:
    - `IObjectStorageAdapter`
    - `Exceptions` (notably `Exceptions.ObjectNotFound`)
- Required runtime inputs:
  - `bucket_name`, `access_key_id`, `secret_access_key`
- Optional:
  - `base_prefix`: prepended to all operations (trailing `/` is removed on init)
  - `session_token`: for temporary credentials
  - `endpoint_url`: for non-AWS S3 endpoints (e.g., MinIO)

## Usage
```python
from queue import Queue
from naas_abi_core.services.object_storage.adapters.secondary.ObjectStorageSecondaryAdapterS3 import (
    ObjectStorageSecondaryAdapterS3,
)

adapter = ObjectStorageSecondaryAdapterS3(
    bucket_name="my-bucket",
    access_key_id="AKIA...",
    secret_access_key="SECRET...",
    base_prefix="my/app",
    endpoint_url=None,  # or "https://s3.amazonaws.com" / MinIO endpoint
)

adapter.put_object("data", "hello.txt", b"hello world")
content = adapter.get_object("data", "hello.txt")
print(content.decode())

q = Queue()
items = adapter.list_objects("data", queue=q)
print(items)

adapter.delete_object("data", "hello.txt")
```

## Caveats
- `list_objects(prefix)` raises `Exceptions.ObjectNotFound` when the prefix has no objects (it checks existence by listing with `MaxKeys=1`).
- `list_objects` returns both:
  - object keys at the requested depth, and
  - “subfolder” prefixes (from `CommonPrefixes`)
  with `base_prefix` removed from the returned strings.
- Errors other than S3 “not found” (`404` / `NoSuchKey`) are re-raised as the original `ClientError`.
