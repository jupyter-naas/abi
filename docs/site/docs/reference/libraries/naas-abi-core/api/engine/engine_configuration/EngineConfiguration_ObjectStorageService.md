# EngineConfiguration_ObjectStorageService

## What it is
Pydantic-based configuration models and loaders for wiring an `ObjectStorageService` with a selectable object storage adapter (`fs`, `s3`, `naas`, or `custom`).

## Public API
- `ObjectStorageAdapterFSConfiguration`
  - Filesystem adapter config model.
  - Fields: `base_path: str`
- `ObjectStorageAdapterS3Configuration`
  - S3 adapter config model.
  - Fields: `bucket_name: str`, `base_prefix: str`, `access_key_id: str`, `secret_access_key: str`, `session_token: str|None`, `endpoint_url: str|None`
- `ObjectStorageAdapterNaasConfiguration`
  - Naas adapter config model.
  - Fields: `naas_api_key: str`, `workspace_id: str`, `storage_name: str`, `base_prefix: str = ""`
- `ObjectStorageAdapterConfiguration` *(inherits `GenericLoader`)*
  - Selects and instantiates an adapter implementation.
  - Fields:
    - `adapter: Literal["fs", "s3", "naas", "custom"]`
    - `config: Union[...config models...] | None`
  - Methods:
    - `validate_adapter() -> Self`: validates `config` matches the selected adapter (and is present unless `adapter="custom"`).
    - `load() -> IObjectStorageAdapter`: returns an instantiated adapter.
- `ObjectStorageServiceConfiguration`
  - Top-level service config wrapper.
  - Fields: `object_storage_adapter: ObjectStorageAdapterConfiguration`
  - Methods:
    - `load() -> ObjectStorageService`: constructs `ObjectStorageService(adapter=...)`.

## Configuration/Dependencies
- Uses **Pydantic v2** (`BaseModel`, `model_validator`, `ConfigDict(extra="forbid")`).
- Adapter selection:
  - `adapter="fs"` loads `ObjectStorageSecondaryAdapterFS`
  - `adapter="s3"` loads `ObjectStorageSecondaryAdapterS3`
  - `adapter="naas"` loads `ObjectStorageSecondaryAdapterNaas`
  - `adapter="custom"` delegates to `GenericLoader.load()` (behavior defined in `GenericLoader`).
- Validation helper: `pydantic_model_validator(...)` is used to ensure `config` conforms to the correct adapter config model.
- All configuration models forbid unknown fields (`extra="forbid"`).

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
- If `adapter != "custom"`, `config` is required; otherwise an `AssertionError` is raised.
- If `adapter` is `fs`/`s3`/`naas`, `config` must match the corresponding config model or validation will fail.
- `adapter="custom"` requires `GenericLoader`-specific configuration (not shown in this file).
