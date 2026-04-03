# ObjectStorageFactory

## What it is
- A small factory class that instantiates `ObjectStorageService` configured with a specific secondary adapter:
  - Local filesystem (FS)
  - AWS S3
  - Naas object storage
- Provides convenience constructors as `@staticmethod`s.

## Public API
### Class: `ObjectStorageFactory`
Static factory methods returning an `ObjectStorageService`:

- `ObjectStorageServiceFS__find_storage(needle: str = "storage") -> ObjectStorageService`
  - Creates an FS-backed service using a storage folder resolved from the current working directory via `find_storage_folder(os.getcwd())`.
  - Note: the `needle` argument is present but not used in the current implementation.

- `ObjectStorageServiceFS(base_path: str) -> ObjectStorageService`
  - Creates an FS-backed service rooted at `base_path`.

- `ObjectStorageServiceS3(access_key_id: str, secret_access_key: str, bucket_name: str, base_prefix: str, session_token: str | None = None) -> ObjectStorageService`
  - Creates an S3-backed service using the provided AWS credentials, bucket, and base prefix.

- `ObjectStorageServiceNaas(naas_api_key: str, workspace_id: str, storage_name: str, base_prefix: str = "") -> ObjectStorageService`
  - Creates a Naas-backed service using the provided Naas API key, workspace ID, storage name, and optional base prefix.

## Configuration/Dependencies
- Depends on:
  - `ObjectStorageService`
  - Secondary adapters:
    - `ObjectStorageSecondaryAdapterFS`
    - `ObjectStorageSecondaryAdapterS3`
    - `ObjectStorageSecondaryAdapterNaas`
  - Utility: `find_storage_folder` (used by `ObjectStorageServiceFS__find_storage`)
- Credentials/parameters are passed directly to the underlying adapters; any further configuration is handled by those adapters/services.

## Usage
```python
from naas_abi_core.services.object_storage.ObjectStorageFactory import ObjectStorageFactory

# Local filesystem storage at an explicit path
svc = ObjectStorageFactory.ObjectStorageServiceFS("/tmp/my-storage")

# S3-backed storage
s3_svc = ObjectStorageFactory.ObjectStorageServiceS3(
    access_key_id="AKIA...",
    secret_access_key="SECRET...",
    bucket_name="my-bucket",
    base_prefix="my/app/prefix",
)

# Naas-backed storage
naas_svc = ObjectStorageFactory.ObjectStorageServiceNaas(
    naas_api_key="naas_api_key",
    workspace_id="workspace_id",
    storage_name="storage_name",
    base_prefix="optional/prefix",
)
```

## Caveats
- `ObjectStorageServiceFS__find_storage()` ignores its `needle` parameter in the current code.
- `ObjectStorageServiceFS__find_storage()` resolves the base path from `os.getcwd()`; behavior depends on the current working directory and `find_storage_folder` implementation.
