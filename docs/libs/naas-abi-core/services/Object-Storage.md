# Object Storage Service

`ObjectStorageService` is the generic blob/file service used by modules and other services.

Related pages: [[services/Triple-Store]], [[services/Overview]].

## Core API

- `get_object(prefix, key) -> bytes`
- `put_object(prefix, key, content)`
- `delete_object(prefix, key)`
- `list_objects(prefix="") -> list[str]`

## Adapter options

- `fs`: local filesystem.
- `s3`: AWS S3 compatible adapter (also works with MinIO via endpoint URL).
- `naas`: Naas-managed storage credentials to S3 backend.
- `custom`: pluggable adapter.

## Path normalization behavior

`ObjectStorageService` strips a leading `storage/` prefix from requests. This prevents duplicate `storage/storage/...` paths when using FS adapter.

## Config examples

Filesystem:

```yaml
services:
  object_storage:
    object_storage_adapter:
      adapter: "fs"
      config:
        base_path: "storage/datastore"
```

S3/MinIO:

```yaml
services:
  object_storage:
    object_storage_adapter:
      adapter: "s3"
      config:
        bucket_name: "my-bucket"
        base_prefix: "abi"
        access_key_id: "{{ secret.AWS_ACCESS_KEY_ID }}"
        secret_access_key: "{{ secret.AWS_SECRET_ACCESS_KEY }}"
        endpoint_url: "http://localhost:9000"
```
