# EngineConfiguration_VectorStoreService

## What it is
Pydantic-based configuration models to wire a `VectorStoreService` with a selectable vector store adapter (`qdrant`, `qdrant_in_memory`, `sqlite_vec`, `nats_rpc`, or `custom`). Includes validation, lazy adapter imports, and helper reporting of local storage location.

## Public API

### Configuration models
- `VectorStoreAdapterQdrantConfiguration` (`pydantic.BaseModel`)
  - Purpose: Schema for the `qdrant` adapter configuration.
  - Fields:
    - `host: str = "localhost"`
    - `port: int = 6333`
    - `api_key: str | None = None`
    - `https: bool = False`
    - `timeout: int = 30`
  - Notes: `extra="forbid"` (unknown fields rejected).

- `VectorStoreAdapterQdrantInMemoryConfiguration` (`pydantic.BaseModel`)
  - Purpose: Schema for the `qdrant_in_memory` adapter configuration.
  - Fields:
    - `storage_path: str = ":memory:"`
    - `timeout: int = 300`
  - Notes: `extra="forbid"`.

- `VectorStoreAdapterSqliteVecConfiguration` (`pydantic.BaseModel`)
  - Purpose: Schema for the `sqlite_vec` adapter configuration.
  - Fields:
    - `persistence_path: str`
    - `journal_mode: str = "WAL"`
    - `busy_timeout_ms: int = 5000`
  - Notes: `extra="forbid"`.

- `VectorStoreAdapterNATSConfiguration` (`pydantic.BaseModel`)
  - Purpose: Schema for the `nats_rpc` adapter configuration (RPC client).
  - Fields:
    - `nats_url: str = "nats://127.0.0.1:4222"`
    - `jwt_secret: str`
    - `service_identity: str = "api"`
  - Notes: `extra="forbid"`.

### Adapter selector/loader
- `VectorStoreAdapterConfiguration` (`GenericLoader`)
  - Purpose: Selects an adapter and holds a raw `config` dict; validates and instantiates the correct adapter implementation.
  - Fields:
    - `adapter: Literal["qdrant", "qdrant_in_memory", "sqlite_vec", "nats_rpc", "custom"]`
    - `config: dict | None = None`
  - Methods:
    - `validate_adapter() -> Self`
      - Ensures `config` is provided when `adapter != "custom"`.
      - Validates `config` against the corresponding Pydantic model via `pydantic_model_validator(...)`.
    - `load() -> IVectorStorePort`
      - Lazy-imports and instantiates the adapter:
        - `"qdrant"` → `QdrantAdapter(**config)`
        - `"qdrant_in_memory"` → `QdrantInMemoryAdapter(**config)`
        - `"sqlite_vec"` → `SqliteVecAdapter(**config)`
        - `"nats_rpc"` → `VectorStoreSecondaryAdapterNATSClient(**config)`
      - `"custom"` → delegates to `GenericLoader.load()`.
    - `local_storage() -> str | None`
      - Returns a human-readable description of where vectors are stored for:
        - `"qdrant_in_memory"` (in-process memory or embedded path)
        - `"sqlite_vec"` (SQLite file path)
        - `"custom"` (delegates to `custom_local_storage()`)
      - Returns `None` for `"qdrant"` and `"nats_rpc"`.

### Service configuration
- `VectorStoreServiceConfiguration` (`pydantic.BaseModel`)
  - Purpose: Top-level configuration for building a `VectorStoreService`.
  - Fields:
    - `vector_store_adapter: VectorStoreAdapterConfiguration`
  - Methods:
    - `load() -> VectorStoreService`
      - Returns `VectorStoreService(adapter=vector_store_adapter.load())`.

## Configuration/Dependencies
- Depends on:
  - `pydantic` (`BaseModel`, `ConfigDict`, `model_validator`)
  - `naas_abi_core.engine.engine_configuration.EngineConfiguration_GenericLoader.GenericLoader`
  - `naas_abi_core.engine.engine_configuration.EngineConfiguration_GenericLoader.config_model`
  - `naas_abi_core.engine.engine_configuration.utils.PydanticModelValidator.pydantic_model_validator`
  - `naas_abi_core.services.vector_store.VectorStoreService`
  - `naas_abi_core.services.vector_store.IVectorStorePort`
- Lazy-loaded adapter implementations:
  - `naas_abi_core.services.vector_store.adapters.QdrantAdapter.QdrantAdapter`
  - `naas_abi_core.services.vector_store.adapters.QdrantInMemoryAdapter.QdrantInMemoryAdapter`
  - `naas_abi_core.services.vector_store.adapters.SqliteVecAdapter.SqliteVecAdapter`
  - `naas_abi_core.services.vector_store.adapters.secondary.VectorStoreSecondaryAdapterNATSClient.VectorStoreSecondaryAdapterNATSClient`

## Usage

```python
from naas_abi_core.engine.engine_configuration.EngineConfiguration_VectorStoreService import (
    VectorStoreServiceConfiguration,
)

cfg = VectorStoreServiceConfiguration(
    vector_store_adapter={
        "adapter": "qdrant_in_memory",
        "config": {"storage_path": ":memory:", "timeout": 300},
    }
)

service = cfg.load()  # VectorStoreService backed by the loaded adapter
where = cfg.vector_store_adapter.local_storage()
print(where)  # "embedded Qdrant in this process"
```

## Caveats
- For `adapter` values other than `"custom"`, `config` is required; missing `config` triggers an `AssertionError`.
- `config` is validated per adapter; unknown fields are rejected (`extra="forbid"`).
- `"custom"` adapter behavior (including `custom_local_storage()` / `GenericLoader.load()`) is defined in `GenericLoader`, not in this file.
- `local_storage()` returns `None` for `"qdrant"` and `"nats_rpc"` (not local to this engine/process).
