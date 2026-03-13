# EngineConfiguration_VectorStoreService

## What it is
Pydantic-based configuration models to validate and construct a `VectorStoreService` with a pluggable vector store adapter (`qdrant`, `qdrant_in_memory`, or `custom`).

## Public API
- `class VectorStoreAdapterQdrantConfiguration(BaseModel)`
  - Validates configuration for the `qdrant` adapter.
  - Fields:
    - `host: str = "localhost"`
    - `port: int = 6333`
    - `api_key: str | None = None`
    - `https: bool = False`
    - `timeout: int = 30`
  - `extra="forbid"` (unknown fields rejected).

- `class VectorStoreAdapterQdrantInMemoryConfiguration(BaseModel)`
  - Validates configuration for the `qdrant_in_memory` adapter.
  - No fields; `extra="forbid"`.

- `class VectorStoreAdapterConfiguration(GenericLoader)`
  - Selects an adapter and validates its `config`.
  - Fields:
    - `adapter: Literal["qdrant", "qdrant_in_memory", "custom"]`
    - `config: dict | None = None`
  - Methods:
    - `validate_adapter(self) -> VectorStoreAdapterConfiguration` (Pydantic `@model_validator(mode="after")`)
      - Requires `config` when `adapter != "custom"`.
      - Validates `config` against the adapter-specific Pydantic model via `pydantic_model_validator(...)`.
    - `load(self) -> IVectorStorePort`
      - For `qdrant`: lazily imports and instantiates `QdrantAdapter(**config)`.
      - For `qdrant_in_memory`: lazily imports and instantiates `QdrantInMemoryAdapter(**config)`.
      - For `custom`: delegates to `GenericLoader.load()`.

- `class VectorStoreServiceConfiguration(BaseModel)`
  - Fields:
    - `vector_store_adapter: VectorStoreAdapterConfiguration`
  - Methods:
    - `load(self) -> VectorStoreService`
      - Returns `VectorStoreService(adapter=self.vector_store_adapter.load())`.

## Configuration/Dependencies
- Depends on:
  - `pydantic` (`BaseModel`, `ConfigDict`, `model_validator`)
  - `naas_abi_core.services.vector_store.VectorStoreService`
  - `naas_abi_core.services.vector_store.IVectorStorePort`
  - Adapter implementations are lazily imported:
    - `naas_abi_core.services.vector_store.adapters.QdrantAdapter.QdrantAdapter`
    - `naas_abi_core.services.vector_store.adapters.QdrantInMemoryAdapter.QdrantInMemoryAdapter`
- Validation helper:
  - `pydantic_model_validator(model_cls, data, message)` is used to validate adapter `config`.

## Usage
```python
from naas_abi_core.engine.engine_configuration.EngineConfiguration_VectorStoreService import (
    VectorStoreServiceConfiguration,
)

cfg = VectorStoreServiceConfiguration.model_validate(
    {
        "vector_store_adapter": {
            "adapter": "qdrant",
            "config": {
                "host": "localhost",
                "port": 6333,
                "api_key": None,
                "https": False,
                "timeout": 30,
            },
        }
    }
)

vector_store_service = cfg.load()
```

## Caveats
- `config` is required for all adapters except `custom`; missing `config` triggers an `AssertionError`.
- For `qdrant` and `qdrant_in_memory`, extra/unknown keys in `config` are rejected (`extra="forbid"`).
- `custom` adapter behavior depends on `GenericLoader.load()` (not defined in this module).
