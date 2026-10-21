# EngineConfiguration_ObjectStorageService

## What it is
Pydantic configuration models for wiring an `ObjectStorageService` with a selectable object storage adapter (`fs`, `s3`, `naas`, `r2`, `nats_rpc`, or `custom`), plus loader helpers to instantiate the configured adapter.

## Public API

### Classes

- `ObjectStorageAdapterFSConfiguration`
  - Filesystem adapter config.
  - Fields:
    - `base_path: str`
  - `extra="forbid"` (unknown fields rejected)

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
  - Naas adapter config.
  - Fields:
    - `naas_api_key: str`
    - `workspace_id: str`
    - `storage_name: str`
    - `base_prefix: str = ""`
  - `extra="forbid"`

- `ObjectStorageAdapterR2Configuration`
  - Cloudflare R2 adapter config.
  - Fields:
    - `account_id: str`
    - `bucket_name: str`
    - `access_key_id: str`
    - `secret_access_key: str`
    - `base_prefix: str = ""`
  - `extra="forbid"`

- `ObjectStorageAdapterNATSConfiguration`
  - NATS RPC client adapter config (talks to a remote object storage service over NATS request/reply).
  - Fields:
    - `nats_url: str = "nats://127.0.0.1:4222"`
    - `jwt_secret: str`
    - `service_identity: str = "api"`
  - `extra="forbid"`

- `ObjectStorageAdapterConfiguration` (extends `GenericLoader`)
  - Selects an adapter and loads an `IObjectStorageAdapter`.
  - Fields:
    - `adapter: Literal["fs", "s3", "naas", "r2", "nats_rpc", "custom"]`
    - `config: (FS|S3|Naas|R2|NATS)|None = None`
  - Methods:
    - `validate_adapter() -> Self` (Pydantic `@model_validator(mode="after")`)
      - Asserts `config` is present when `adapter != "custom"`.
      - Validates `config` against the adapter-specific pydantic model via `pydantic_model_validator(...)`.
    - `load() -> IObjectStorageAdapter`
      - For `fs`/`s3`/`naas`/`r2`/`nats_rpc`: imports and instantiates the corresponding secondary adapter using `**config.model_dump()`.
      - For `custom`: delegates to `GenericLoader.load()`.
    - `local_storage() -> str | None`
      - Returns a human-readable description of where objects live:
        - `fs`: `"files under {base_path}"`
        - `custom`: delegates to `self.custom_local_storage()`
        - others: `None`

- `ObjectStorageServiceConfiguration`
  - Top-level service configuration.
  - Fields:
    - `object_storage_adapter: ObjectStorageAdapterConfiguration`
  - Methods:
    - `load() -> ObjectStorageService`: builds `ObjectStorageService(adapter=...)`.

## Configuration/Dependencies

- Uses **Pydantic v2**: `BaseModel`, `ConfigDict`, `model_validator`.
- Depends on:
  - `GenericLoader`, `config_model` from `naas_abi_core.engine.engine_configuration.EngineConfiguration_GenericLoader`
  - `pydantic_model_validator` from `naas_abi_core.engine.engine_configuration.utils.PydanticModelValidator`
  - `ObjectStorageService`, `IObjectStorageAdapter`
- Adapter implementations are imported at load time:
  - `naas_abi_core.services.object_storage.adapters.secondary.ObjectStorageSecondaryAdapterFS`
  - `naas_abi_core.services.object_storage.adapters.secondary.ObjectStorageSecondaryAdapterS3`
  - `naas_abi_core.services.object_storage.adapters.secondary.ObjectStorageSecondaryAdapterNaas`
  - `naas_abi_core.services.object_storage.adapters.secondary.ObjectStorageSecondaryAdapterR2`
  - `naas_abi_core.services.object_storage.adapters.secondary.ObjectStorageSecondaryAdapterNATSClient`

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
print(cfg.object_storage_adapter.local_storage())  # "files under storage/datastore"
```

## Caveats

- `config` is required for all adapters except `custom` (`assert` enforced in both validation and `load()`).
- All adapter config models set `extra="forbid"`: unknown fields cause validation errors.
- `adapter="custom"` bypasses built-in instantiation and uses `GenericLoader` behavior (not defined in this file).
- `local_storage()` only reports a location for `fs` and `custom`; returns `None` for `s3`, `naas`, `r2`, and `nats_rpc`.
