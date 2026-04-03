# ObjectStorageSecondaryAdapterNaas

## What it is
- A Naas-specific secondary adapter implementing `IObjectStorageAdapter`.
- Fetches temporary S3-compatible credentials from the Naas API, instantiates an internal `ObjectStorageSecondaryAdapterS3`, and delegates object operations to it.
- Automatically refreshes credentials when they expire.

## Public API
### Classes
- `Credentials` (dataclass)
  - Holds S3 credential material and metadata:
    - `bucket_name`, `bucket_prefix`, `access_key_id`, `secret_key`, `session_token`, `region_name`, `created_at`.

- `ObjectStorageSecondaryAdapterNaas(IObjectStorageAdapter)`
  - `__init__(naas_api_key: str, workspace_id: str, storage_name: str, base_prefix: str = "")`
    - Configures Naas API access and an optional `base_prefix` appended to the storage prefix.
  - `ensure_credentials() -> Credentials`
    - Ensures credentials exist and refreshes them if older than `CREDENTIALS_EXPIRATION_TIME` (20 minutes).
  - `get_object(prefix: str, key: str) -> bytes`
    - Returns the object bytes by delegating to the underlying S3 adapter.
  - `put_object(prefix: str, key: str, content: bytes)`
    - Uploads object content by delegating to the underlying S3 adapter.
  - `delete_object(prefix: str, key: str)`
    - Deletes an object by delegating to the underlying S3 adapter.
  - `list_objects(prefix: str, queue: Optional[Queue] = None) -> list[str]`
    - Lists objects under a prefix by delegating to the underlying S3 adapter.

## Configuration/Dependencies
- External services:
  - Naas API endpoint: `https://api.naas.ai/`
  - Credentials endpoint (POST): `/workspace/{workspace_id}/storage/credentials/` with JSON `{ "name": storage_name }`
  - Authorization header: `Bearer {naas_api_key}`
- Credential refresh:
  - `CREDENTIALS_EXPIRATION_TIME = timedelta(minutes=20)`
- Python dependencies:
  - `requests` (HTTP calls; uses `response.raise_for_status()`)
  - `pydash.get` (extract nested JSON fields)
- Internal dependency:
  - `ObjectStorageSecondaryAdapterS3` (used for actual object storage operations)

## Usage
```python
from naas_abi_core.services.object_storage.adapters.secondary.ObjectStorageSecondaryAdapterNaas import (
    ObjectStorageSecondaryAdapterNaas,
)

adapter = ObjectStorageSecondaryAdapterNaas(
    naas_api_key="YOUR_NAAS_API_KEY",
    workspace_id="YOUR_WORKSPACE_ID",
    storage_name="YOUR_STORAGE_NAME",
    base_prefix="my/app",  # optional
)

adapter.put_object(prefix="data", key="hello.txt", content=b"hello")
data = adapter.get_object(prefix="data", key="hello.txt")
print(data.decode("utf-8"))

keys = adapter.list_objects(prefix="data")
print(keys)

adapter.delete_object(prefix="data", key="hello.txt")
```

## Caveats
- Credential refresh is time-based only; it refreshes when `created_at` is older than 20 minutes.
- `__refresh_credentials()` parses `bucket_name` and `bucket_prefix` from `credentials.s3.endpoint_url` by splitting on `/`; unexpected endpoint URL formats can break parsing.
- Errors from the Naas API are raised via `requests.Response.raise_for_status()`.
