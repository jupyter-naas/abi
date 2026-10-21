# ObjectStorageSecondaryAdapterS3

## What it is
- An S3-backed implementation of `IObjectStorageAdapter` using `boto3`.
- Provides basic object operations (get/put/delete/list) and metadata retrieval within a bucket, optionally scoped under a `base_prefix`.

## Public API
- `class ObjectStorageSecondaryAdapterS3(IObjectStorageAdapter)`
  - `__init__(bucket_name, access_key_id, secret_access_key, base_prefix="", session_token=None, endpoint_url=None)`
    - Creates a boto3 S3 client for the target bucket; optionally uses a custom `endpoint_url` and `base_prefix`.
  - `get_object(prefix: str, key: str) -> bytes`
    - Downloads an object and returns its content as bytes.
  - `put_object(prefix: str, key: str, content: bytes) -> None`
    - Uploads bytes content to the given key.
  - `delete_object(prefix: str, key: str) -> None`
    - Deletes an existing object.
  - `list_objects(prefix: str, queue: Optional[Queue] = None) -> list[str]`
    - Lists direct children (depth=1) under a prefix (uses S3 `Delimiter="/"`).
    - Optionally pushes each returned key into the provided `queue`.
  - `get_object_metadata(prefix: str, key: str) -> ObjectMetaData`
    - Returns `ObjectMetaData` built from S3 `head_object` (size, last modified, content type, and an `s3://...` path).

## Configuration/Dependencies
- Dependencies:
  - `boto3`
  - `botocore.exceptions.ClientError`
  - `naas_abi_core.services.object_storage.ObjectStoragePort`:
    - `IObjectStorageAdapter`, `ObjectMetaData`, `Exceptions` (notably `Exceptions.ObjectNotFound`)
- Required inputs:
  - `bucket_name`, `access_key_id`, `secret_access_key`
- Optional inputs:
  - `base_prefix`: prepended to all operations (normalized; trailing `/` removed)
  - `session_token`: for temporary credentials
  - `endpoint_url`: for S3-compatible endpoints (e.g., MinIO)

## Usage
```python
from naas_abi_core.services.object_storage.adapters.secondary.ObjectStorageSecondaryAdapterS3 import (
    ObjectStorageSecondaryAdapterS3,
)

adapter = ObjectStorageSecondaryAdapterS3(
    bucket_name="my-bucket",
    access_key_id="AKIA...",
    secret_access_key="SECRET...",
    base_prefix="my/app",
    # endpoint_url="http://localhost:9000",  # optional for S3-compatible storage
)

adapter.put_object("data", "hello.txt", b"hello")
data = adapter.get_object("data", "hello.txt")
print(data.decode())

print(adapter.list_objects("data"))  # depth-1 listing

meta = adapter.get_object_metadata("data", "hello.txt")
print(meta.file_path, meta.file_size_bytes)

adapter.delete_object("data", "hello.txt")
```

## Caveats
- Existence checks:
  - `get_object`, `delete_object`, `list_objects`, and `get_object_metadata` call an internal existence check and raise `Exceptions.ObjectNotFound` when missing.
  - Prefix existence is determined by `list_objects_v2` with `MaxKeys=1`; empty prefixes are treated as “not found”.
- `list_objects` returns keys/prefixes **relative to `base_prefix`** (the adapter strips `base_prefix/` from results) and lists only one level deep due to `Delimiter="/"`.
