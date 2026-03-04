# EngineConfiguration_TripleStoreService

## What it is
Pydantic-based configuration models for wiring a `TripleStoreService` with a selectable backend (“adapter”). It validates adapter-specific config and lazily imports/instantiates the correct triple store port implementation.

## Public API
- `OxigraphAdapterConfiguration` (pydantic `BaseModel`)
  - Config for the `oxigraph` adapter (`oxigraph_url`, `timeout`).
- `ApacheJenaTDB2AdapterConfiguration` (pydantic `BaseModel`)
  - Config for the `apache_jena_tdb2` adapter (`jena_tdb2_url`, `timeout`).
- `AWSNeptuneAdapterConfiguration` (pydantic `BaseModel`)
  - Config for the `aws_neptune` adapter (`aws_region_name`, `aws_access_key_id`, `aws_secret_access_key`, `db_instance_identifier`).
- `AWSNeptuneSSHTunnelAdapterConfiguration` (pydantic `BaseModel`)
  - Extends `AWSNeptuneAdapterConfiguration` with SSH tunnel/bastion fields.
- `TripleStoreAdapterFilesystemConfiguration` (pydantic `BaseModel`)
  - Config for the `fs` adapter (`store_path`, `triples_path`).
- `TripleStoreAdapterObjectStorageConfiguration` (pydantic `BaseModel`)
  - Config for the `object_storage` adapter (`object_storage_service`, `triples_prefix`).
- `TripleStoreAdapterConfiguration` (`GenericLoader`)
  - Fields:
    - `adapter`: one of `"oxigraph" | "apache_jena_tdb2" | "aws_neptune_sshtunnel" | "aws_neptune" | "fs" | "object_storage" | "custom"`
    - `config`: adapter-specific config model, `dict`, or `None`
  - Methods:
    - `validate_adapter() -> Self`: pydantic model validator; enforces `config` presence for non-`custom` adapters and validates shape by adapter.
    - `load() -> ITripleStorePort`: instantiates and returns the configured adapter (or delegates to `GenericLoader.load()` when `adapter == "custom"`).
- `TripleStoreServiceConfiguration` (pydantic `BaseModel`)
  - Fields:
    - `triple_store_adapter: TripleStoreAdapterConfiguration`
  - Methods:
    - `load() -> TripleStoreService`: constructs `TripleStoreService(triple_store_adapter=...)`.

## Configuration/Dependencies
- Uses **Pydantic v2** features:
  - `ConfigDict(extra="forbid")` on adapter config models (unknown fields rejected).
  - `@model_validator(mode="after")` for cross-field validation.
- Depends on:
  - `GenericLoader` (for `"custom"` adapter behavior)
  - `pydantic_model_validator` utility for validating `config` objects
  - `ObjectStorageServiceConfiguration` for the object storage adapter
  - Triple store service/ports:
    - `ITripleStorePort`
    - `TripleStoreService`
- Lazy-imported adapter implementations (imported only when selected):
  - `Oxigraph`
  - `ApacheJenaTDB2`
  - `AWSNeptune`, `AWSNeptuneSSHTunnel`
  - `TripleStoreService__SecondaryAdaptor__Filesystem`
  - `TripleStoreService__SecondaryAdaptor__ObjectStorage`

## Usage
Minimal example using the filesystem adapter:

```python
from naas_abi_core.engine.engine_configuration.EngineConfiguration_TripleStoreService import (
    TripleStoreServiceConfiguration,
    TripleStoreAdapterConfiguration,
    TripleStoreAdapterFilesystemConfiguration,
)

cfg = TripleStoreServiceConfiguration(
    triple_store_adapter=TripleStoreAdapterConfiguration(
        adapter="fs",
        config=TripleStoreAdapterFilesystemConfiguration(
            store_path="storage/triplestore",
            triples_path="triples",
        ),
    )
)

service = cfg.load()  # -> TripleStoreService
```

## Caveats
- For any adapter other than `"custom"`, `config` is required; otherwise validation/assertions will fail.
- Adapter config models forbid extra fields (`extra="forbid"`).
- `"custom"` adapter delegates to `GenericLoader.load()`; its expected shape/behavior is defined by `GenericLoader`, not by this module.
- Unknown `adapter` values raise `ValueError("Adapter ... not supported")`.
