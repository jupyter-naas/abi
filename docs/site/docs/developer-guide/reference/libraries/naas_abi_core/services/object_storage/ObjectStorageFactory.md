# ObjectStorageFactory

## What it is
- A small factory module that builds `ObjectStorageService` instances backed by different secondary adapters:
  - Local filesystem (FS)
  - AWS S3
  - Naas object storage

## Public API
- `class ObjectStorageFactory`
  - `ObjectStorageServiceFS__find_storage(needle: str = "storage") -> ObjectStorageService`
    - Creates an FS-backed `ObjectStorageService` using a storage folder discovered from the current working directory via `find_storage_folder(os.getcwd())`.
  - `ObjectStorageServiceFS(base_path: str) -> ObjectStorageService`
    - Creates an FS-backed `ObjectStorageService` rooted at `base_path`.
  - `ObjectStorageServiceS3(access_key_id: str, secret_access_key: str, bucket_name: str, base_prefix: str, session_token: str | None = None) -> ObjectStorageService`
    - Creates an S3-backed `ObjectStorageService` configured for the given bucket and prefix.
  - `ObjectStorageServiceNaas(naas_api_key: str, workspace_id: str, storage_name: str, base_prefix: str = "") -> ObjectStorageService`
    - Creates a Naas-backed `ObjectStorageService` configured for the given workspace and storage name.

## Configuration/Dependencies
- Imports and composes:
  - `ObjectStorageService`
  - `ObjectStorageSecondaryAdapterFS`
  - `ObjectStorageSecondaryAdapterS3`
  - `ObjectStorageSecondaryAdapterNaas`
  - `find_storage_folder` from `naas_abi_core.utils.Storage`
- `ObjectStorageServiceFS__find_storage` depends on:
  - `os.getcwd()` as the starting point for storage discovery.

## Usage
```python
from naas_abi_core.services.object_storage.ObjectStorageFactory import ObjectStorageFactory

# Local filesystem storage at a known path
svc_fs = ObjectStorageFactory.ObjectStorageServiceFS("/tmp/my-storage")

# Local filesystem storage discovered relative to current working directory
svc_fs_auto = ObjectStorageFactory.ObjectStorageServiceFS__find_storage()

# AWS S3-backed storage
svc_s3 = ObjectStorageFactory.ObjectStorageServiceS3(
    access_key_id="AKIA...",
    secret_access_key="SECRET...",
    bucket_name="my-bucket",
    base_prefix="my/prefix",
)

# Naas-backed storage
svc_naas = ObjectStorageFactory.ObjectStorageServiceNaas(
    naas_api_key="naas-api-key",
    workspace_id="workspace-id",
    storage_name="storage-name",
    base_prefix="optional/prefix",
)
```

## Caveats
- `ObjectStorageServiceFS__find_storage` ignores its `needle` parameter; storage discovery is delegated solely to `find_storage_folder(os.getcwd())`.
