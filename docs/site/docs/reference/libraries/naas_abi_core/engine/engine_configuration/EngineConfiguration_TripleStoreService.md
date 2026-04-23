# TripleStoreServiceConfiguration

## What it is
Pydantic-based configuration models for selecting and instantiating a `TripleStoreService` with a pluggable triple-store adapter (Oxigraph, Apache Jena TDB2/Fuseki, AWS Neptune, filesystem, embedded Oxigraph, object storage, or a custom loader).

## Public API
- `OxigraphAdapterConfiguration` (pydantic model)
  - Fields: `oxigraph_url: str = "http://localhost:7878"`, `timeout: int = 60`
  - Purpose: Configure the `"oxigraph"` adapter.
- `ApacheJenaTDB2AdapterConfiguration` (pydantic model)
  - Fields: `jena_tdb2_url: str = "http://localhost:3030/ds"`, `timeout: int = 60`, `key_value_service: KeyValueServiceConfiguration | None = None`
  - Purpose: Configure the `"apache_jena_tdb2"` adapter; optionally includes a key-value service for a distributed write lock.
- `AWSNeptuneAdapterConfiguration` (pydantic model)
  - Fields: `aws_region_name: str`, `aws_access_key_id: str`, `aws_secret_access_key: str`, `db_instance_identifier: str`
  - Purpose: Configure the `"aws_neptune"` adapter.
- `AWSNeptuneSSHTunnelAdapterConfiguration` (pydantic model; extends `AWSNeptuneAdapterConfiguration`)
  - Additional fields: `bastion_host: str`, `bastion_port: int`, `bastion_user: str`, `bastion_private_key: str`
  - Purpose: Configure the `"aws_neptune_sshtunnel"` adapter.
- `TripleStoreAdapterFilesystemConfiguration` (pydantic model)
  - Fields: `store_path: str`, `triples_path: str = "triples"`
  - Purpose: Configure the `"fs"` adapter.
- `TripleStoreAdapterOxigraphEmbeddedConfiguration` (pydantic model)
  - Fields: `store_path: str`, `graph_base_iri: str = "http://ontology.naas.ai/graph/default"`
  - Purpose: Configure the `"oxigraph_embedded"` adapter.
- `TripleStoreAdapterObjectStorageConfiguration` (pydantic model)
  - Fields: `object_storage_service: ObjectStorageServiceConfiguration`, `triples_prefix: str = "triples"`
  - Purpose: Configure the `"object_storage"` adapter.
- `TripleStoreAdapterConfiguration` (inherits `GenericLoader`)
  - Fields:
    - `adapter`: one of `"oxigraph" | "apache_jena_tdb2" | "aws_neptune_sshtunnel" | "aws_neptune" | "fs" | "oxigraph_embedded" | "object_storage" | "custom"`
    - `config`: adapter-specific config model, `dict`, or `None`
  - Methods:
    - `validate_adapter() -> Self`: coerces/validates `config` into the correct pydantic model for the selected adapter; requires `config` when `adapter != "custom"`.
    - `load() -> ITripleStorePort`: lazily imports and constructs the configured adapter instance; delegates to `GenericLoader.load()` when `adapter == "custom"`.
- `TripleStoreServiceConfiguration` (pydantic model)
  - Fields: `triple_store_adapter: TripleStoreAdapterConfiguration`
  - Methods:
    - `load() -> TripleStoreService`: constructs `TripleStoreService(triple_store_adapter=...)`.

## Configuration/Dependencies
- Uses **Pydantic v2** (`BaseModel`, `model_validator`, `ConfigDict(extra="forbid")`).
- Adapter-specific dependencies are **lazy-imported** during `TripleStoreAdapterConfiguration.load()`:
  - `"oxigraph"`: `naas_abi_core.services.triple_store.adaptors.secondary.Oxigraph.Oxigraph`
  - `"apache_jena_tdb2"`: `...ApacheJenaTDB2.ApacheJenaTDB2` (optionally loads `key_value_service`)
  - `"aws_neptune"` / `"aws_neptune_sshtunnel"`: `...AWSNeptune.AWSNeptune` / `AWSNeptuneSSHTunnel`
  - `"fs"`: `...TripleStoreService__SecondaryAdaptor__Filesystem`
  - `"oxigraph_embedded"`: `...TripleStoreService__SecondaryAdaptor__OxigraphEmbedded`
  - `"object_storage"`: `...TripleStoreService__SecondaryAdaptor__ObjectStorage`
- Extra fields in adapter config models are forbidden (`extra="forbid"`).
- `"custom"` uses `GenericLoader` behavior (not defined in this file).

## Usage
### Create a service using the filesystem adapter
```python
from naas_abi_core.engine.engine_configuration.EngineConfiguration_TripleStoreService import (
    TripleStoreServiceConfiguration,
    TripleStoreAdapterConfiguration,
)

cfg = TripleStoreServiceConfiguration(
    triple_store_adapter=TripleStoreAdapterConfiguration(
        adapter="fs",
        config={"store_path": "storage/triplestore", "triples_path": "triples"},
    )
)

triple_store_service = cfg.load()
```

### Apache Jena TDB2 with optional key-value service
```python
from naas_abi_core.engine.engine_configuration.EngineConfiguration_TripleStoreService import (
    TripleStoreAdapterConfiguration,
)

adapter_cfg = TripleStoreAdapterConfiguration(
    adapter="apache_jena_tdb2",
    config={
        "jena_tdb2_url": "http://localhost:3030/ds",
        "timeout": 60,
        # "key_value_service": {...}  # KeyValueServiceConfiguration-compatible dict
    },
)

port = adapter_cfg.load()
```

## Caveats
- For any adapter other than `"custom"`, `config` is required; missing `config` triggers an `AssertionError`.
- Validation filters config dict keys to only those defined on the corresponding adapter configuration model before validating.
- `load()` raises `ValueError` for unsupported adapter strings (should not occur if `adapter` matches the declared `Literal`).
