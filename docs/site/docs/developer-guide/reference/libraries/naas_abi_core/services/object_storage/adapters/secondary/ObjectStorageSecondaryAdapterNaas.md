# ObjectStorageSecondaryAdapterNaas

## What it is
- A secondary object storage adapter that fetches temporary S3-compatible credentials from the Naas API and then delegates all object operations to `ObjectStorageSecondaryAdapterS3`.
- Implements `IObjectStorageAdapter`.

## Public API
### Classes
- `Credentials` (dataclass)
  - Holds temporary S3 credential material and metadata:
    - `bucket_name`, `bucket_prefix`, `access_key_id`, `secret_key`, `session_token`, `region_name`, `created_at`.

- `ObjectStorageSecondaryAdapterNaas(IObjectStorageAdapter)`
  - `__init__(naas_api_key: str, workspace_id: str, storage_name: str, base_prefix: str = "")`
    - Stores Naas auth/config and an optional `base_prefix` appended to the storage prefix.
  - `ensure_credentials() -> Credentials`
    - Ensures credentials exist and refreshes them when older than `CREDENTIALS_EXPIRATION_TIME` (20 minutes).
  - `get_object(prefix: str, key: str) -> bytes`
    - Downloads an object via the underlying S3 adapter.
  - `put_object(prefix: str, key: str, content: bytes)`
    - Uploads an object via the underlying S3 adapter.
  - `delete_object(prefix: str, key: str)`
    - Deletes an object via the underlying S3 adapter.
  - `list_objects(prefix: str, queue: Optional[Queue] = None) -> list[str]`
    - Lists objects via the underlying S3 adapter; optionally streams results via a `Queue` (passed through).
  - `get_object_metadata(prefix: str, key: str) -> ObjectMetaData`
    - Fetches object metadata via the underlying S3 adapter.

## Configuration/Dependencies
- External services:
  - Naas API endpoint: `https://api.naas.ai/`
  - Credentials are requested from:
    - `POST /workspace/{workspace_id}/storage/credentials/` with JSON body `{"name": storage_name}`
    - Header `Authorization: Bearer {naas_api_key}`
- Dependencies:
  - `requests` for HTTP calls
  - `pydash.get` for nested JSON access
  - `naas_abi_core.services.object_storage.adapters.secondary.ObjectStorageSecondaryAdapterS3`
- Credential refresh policy:
  - `CREDENTIALS_EXPIRATION_TIME = timedelta(minutes=20)`
  - Refresh occurs when `created_at < now - 20 minutes`.

## Usage
```python
from naas_abi_core.services.object_storage.adapters.secondary.ObjectStorageSecondaryAdapterNaas import (
    ObjectStorageSecondaryAdapterNaas,
)

adapter = ObjectStorageSecondaryAdapterNaas(
    naas_api_key="YOUR_NAAS_API_KEY",
    workspace_id="YOUR_WORKSPACE_ID",
    storage_name="YOUR_STORAGE_NAME",
    base_prefix="my-app",  # optional
)

adapter.put_object(prefix="data", key="hello.txt", content=b"hello")
data = adapter.get_object(prefix="data", key="hello.txt")
print(data.decode("utf-8"))

keys = adapter.list_objects(prefix="data")
print(keys)

meta = adapter.get_object_metadata(prefix="data", key="hello.txt")
print(meta)

adapter.delete_object(prefix="data", key="hello.txt")
```

## Caveats
- HTTP errors from the Naas credentials endpoint will raise via `response.raise_for_status()`.
- `bucket_name` and `bucket_prefix` are derived by splitting `credentials.s3.endpoint_url` on `/`; unexpected endpoint formats may break parsing.
- All operations assert that the internal S3 adapter is initialized after credential retrieval; failures to obtain credentials will prevent any storage operation.
