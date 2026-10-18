# EngineConfiguration_TripleStoreService

## What it is
Pydantic configuration models to validate and instantiate a `TripleStoreService` backed by a selectable triple-store adapter (local/remote implementations, plus a `custom` loader path).

## Public API

### Configuration models (Pydantic)

- `OxigraphAdapterConfiguration`
  - Purpose: Configure the `"oxigraph"` adapter.
  - Fields:
    - `oxigraph_url: str = "http://localhost:7878"`
    - `timeout: int = 60`

- `ApacheJenaTDB2AdapterConfiguration`
  - Purpose: Configure the `"apache_jena_tdb2"` adapter (Fuseki/TDB2), optionally with a key-value service for a distributed write lock.
  - Fields:
    - `jena_tdb2_url: str = "http://localhost:3030/ds"`
    - `timeout: int = 60`
    - `key_value_service: KeyValueServiceConfiguration | None = None`

- `AWSNeptuneAdapterConfiguration`
  - Purpose: Configure the `"aws_neptune"` adapter.
  - Fields:
    - `aws_region_name: str`
    - `aws_access_key_id: str`
    - `aws_secret_access_key: str`
    - `db_instance_identifier: str`

- `AWSNeptuneSSHTunnelAdapterConfiguration` (extends `AWSNeptuneAdapterConfiguration`)
  - Purpose: Configure the `"aws_neptune_sshtunnel"` adapter.
  - Additional fields:
    - `bastion_host: str`
    - `bastion_port: int`
    - `bastion_user: str`
    - `bastion_private_key: str`

- `TripleStoreAdapterFilesystemConfiguration`
  - Purpose: Configure the `"fs"` adapter.
  - Fields:
    - `store_path: str`
    - `triples_path: str = "triples"`

- `TripleStoreAdapterOxigraphEmbeddedConfiguration`
  - Purpose: Configure the `"oxigraph_embedded"` adapter.
  - Fields:
    - `store_path: str`
    - `graph_base_iri: str = "http://ontology.naas.ai/graph/default"`

- `TripleStoreAdapterObjectStorageConfiguration`
  - Purpose: Configure the `"object_storage"` adapter.
  - Fields:
    - `object_storage_service: ObjectStorageServiceConfiguration`
    - `triples_prefix: str = "triples"`

- `TripleStoreAdapterNATSConfiguration`
  - Purpose: Configure the `"nats_rpc"` adapter (NATS request/reply RPC client to a remote triple-store service).
  - Fields:
    - `nats_url: str = "nats://127.0.0.1:4222"`
    - `jwt_secret: str`
    - `service_identity: str = "api"`

### Loader / service configuration

- `TripleStoreAdapterConfiguration` (inherits `GenericLoader`)
  - Purpose: Select an adapter and validate/coerce `config`, then instantiate an `ITripleStorePort`.
  - Fields:
    - `adapter`: one of
      - `"oxigraph" | "apache_jena_tdb2" | "aws_neptune_sshtunnel" | "aws_neptune" | "fs" | "oxigraph_embedded" | "object_storage" | "nats_rpc" | "custom"`
    - `config`: adapter-specific Pydantic model, `dict`, or `None`
  - Methods:
    - `validate_adapter() -> Self` (Pydantic `@model_validator(mode="after")`)
      - Coerces `config` into the correct config model for the selected adapter.
      - Filters dict payloads to only fields defined on the target config model.
      - Requires `config` for any adapter other than `"custom"`.
    - `load() -> ITripleStorePort`
      - Lazy-imports and constructs the configured adapter instance.
      - If `adapter == "custom"`, delegates to `GenericLoader.load()`.
    - `local_storage() -> str | None`
      - Returns a human-readable description of where triples live for some adapters (`fs`, `oxigraph_embedded`, `object_storage`, `custom`), otherwise `None`.

- `TripleStoreServiceConfiguration`
  - Purpose: Wraps `TripleStoreAdapterConfiguration` and builds a `TripleStoreService`.
  - Fields:
    - `triple_store_adapter: TripleStoreAdapterConfiguration`
  - Methods:
    - `load() -> TripleStoreService`: `TripleStoreService(triple_store_adapter=...)`

## Configuration/Dependencies

- Pydantic v2 models use `ConfigDict(extra="forbid")` on adapter config models (unknown fields rejected during validation).
- Adapter implementations are imported lazily inside `TripleStoreAdapterConfiguration.load()`:
  - `"oxigraph"` → `naas_abi_core.services.triple_store.adaptors.secondary.Oxigraph.Oxigraph`
  - `"apache_jena_tdb2"` → `...adaptors.secondary.ApacheJenaTDB2.ApacheJenaTDB2` (optionally loads `key_value_service`)
  - `"aws_neptune"` / `"aws_neptune_sshtunnel"` → `...adaptors.secondary.AWSNeptune.AWSNeptune` / `AWSNeptuneSSHTunnel`
  - `"fs"` → `...adaptors.secondary.TripleStoreService__SecondaryAdaptor__Filesystem.TripleStoreService__SecondaryAdaptor__Filesystem`
  - `"oxigraph_embedded"` → `...adaptors.secondary.TripleStoreService__SecondaryAdaptor__OxigraphEmbedded.TripleStoreService__SecondaryAdaptor__OxigraphEmbedded`
  - `"object_storage"` → `...adaptors.secondary.TripleStoreService__SecondaryAdaptor__ObjectStorage.TripleStoreService__SecondaryAdaptor__ObjectStorage`
  - `"nats_rpc"` → `naas_abi_core.services.triple_store.adapters.secondary.TripleStoreSecondaryAdapterNATSClient.TripleStoreSecondaryAdapterNATSClient`
- `"custom"` uses `GenericLoader` behavior (defined elsewhere).

## Usage

### Minimal: filesystem-backed triple store service
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

service = cfg.load()
```

### Minimal: NATS RPC client adapter
```python
from naas_abi_core.engine.engine_configuration.EngineConfiguration_TripleStoreService import (
    TripleStoreAdapterConfiguration,
)

port = TripleStoreAdapterConfiguration(
    adapter="nats_rpc",
    config={"nats_url": "nats://127.0.0.1:4222", "jwt_secret": "secret", "service_identity": "api"},
).load()
```

## Caveats

- For any adapter other than `"custom"`, `config` is required; missing `config` triggers an `AssertionError`.
- When `config` is a `dict`, validation silently drops unknown keys before model validation (only fields declared on the chosen adapter config are kept).
- `load()` raises `ValueError` if an unsupported `adapter` string somehow bypasses type validation.
