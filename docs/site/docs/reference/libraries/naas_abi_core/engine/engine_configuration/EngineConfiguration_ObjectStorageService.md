# EngineConfiguration_ObjectStorageService

## What it is
Pydantic-based configuration models and loaders for wiring an `ObjectStorageService` with a selectable object storage adapter (`fs`, `s3`, `naas`, or `custom`).

## Public API

### Classes

- `ObjectStorageAdapterFSConfiguration`
  - Filesystem adapter config.
  - Fields: `base_path: str`
  - `extra="forbid"` (unknown fields are rejected)

- `ObjectStorageAdapterS3Configuration`
  - S3-compatible adapter config.
  - Fields:
    - `bucket_name: str`
    - `base_prefix: str`
    - `access_key_id: str`
    - `secret_access_key: str`
    - `session_token: str | None = None`
    - `endpoint_url: str | None = None`
  - `extra="forbid"`

- `ObjectStorageAdapterNaasConfiguration`
  - Naas object storage adapter config.
  - Fields:
    - `naas_api_key: str`
    - `workspace_id: str`
    - `storage_name: str`
    - `base_prefix: str = ""`
  - `extra="forbid"`

- `ObjectStorageAdapterConfiguration` (extends `GenericLoader`)
  - Selects which adapter to instantiate and validates its config.
  - Fields:
    - `adapter: Literal["fs", "s3", "naas", "custom"]`
    - `config: ObjectStorageAdapterFSConfiguration | ObjectStorageAdapterS3Configuration | ObjectStorageAdapterNaasConfiguration | None = None`
  - Methods:
    - `validate_adapter() -> Self` (Pydantic model validator)
      - Requires `config` when `adapter != "custom"`
      - Validates `config` type/shape against the selected adapter model
    - `load() -> IObjectStorageAdapter`
      - For `fs`, `s3`, `naas`: imports and instantiates the corresponding adapter with `config.model_dump()`
      - For `custom`: delegates to `GenericLoader.load()`

- `ObjectStorageServiceConfiguration`
  - Top-level service configuration.
  - Fields: `object_storage_adapter: ObjectStorageAdapterConfiguration`
  - Methods:
    - `load() -> ObjectStorageService`
      - Builds `ObjectStorageService(adapter=...)` using the configured adapter.

## Configuration/Dependencies

- Depends on Pydantic v2 features (`BaseModel`, `ConfigDict`, `model_validator`).
- Adapter-specific implementations are imported at load time:
  - `naas_abi_core.services.object_storage.adapters.secondary.ObjectStorageSecondaryAdapterFS`
  - `naas_abi_core.services.object_storage.adapters.secondary.ObjectStorageSecondaryAdapterS3`
  - `naas_abi_core.services.object_storage.adapters.secondary.ObjectStorageSecondaryAdapterNaas`
- `custom` adapter path is handled by `GenericLoader` (not defined in this file).

## Usage

```python
from naas_abi_core.engine.engine_configuration.EngineConfiguration_ObjectStorageService import (
    ObjectStorageServiceConfiguration,
    ObjectStorageAdapterConfiguration,
    ObjectStorageAdapterFSConfiguration,
)

cfg = ObjectStorageServiceConfiguration(
    object_storage_adapter=ObjectStorageAdapterConfiguration(
        adapter="fs",
        config=ObjectStorageAdapterFSConfiguration(base_path="storage/datastore"),
    )
)

service = cfg.load()  # ObjectStorageService with FS adapter
```

## Caveats

- `config` is required for `adapter` values `fs`, `s3`, and `naas`. Missing it triggers an assertion error.
- Unknown fields in adapter config models are rejected (`extra="forbid"`).
- Selecting `adapter="custom"` bypasses the built-in adapter validation/instantiation and relies on `GenericLoader` behavior.
