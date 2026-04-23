# EngineConfiguration_VectorStoreService

## What it is
Pydantic-based configuration models for wiring a `VectorStoreService` with a selectable vector store adapter (`qdrant`, `qdrant_in_memory`, or `custom`). Includes validation and a `load()` method to instantiate the configured adapter and service.

## Public API
- `VectorStoreAdapterQdrantConfiguration` (Pydantic `BaseModel`)
  - Purpose: Schema for the `qdrant` adapter configuration.
  - Fields:
    - `host: str = "localhost"`
    - `port: int = 6333`
    - `api_key: str | None = None`
    - `https: bool = False`
    - `timeout: int = 30`
  - Notes: `extra="forbid"` (unknown fields rejected).

- `VectorStoreAdapterQdrantInMemoryConfiguration` (Pydantic `BaseModel`)
  - Purpose: Schema for the `qdrant_in_memory` adapter configuration.
  - Fields:
    - `storage_path: str = ":memory:"`
    - `timeout: int = 300`
  - Notes: `extra="forbid"`.

- `VectorStoreAdapterConfiguration` (`GenericLoader`)
  - Purpose: Generic adapter selector + config holder with validation and instantiation.
  - Fields:
    - `adapter: Literal["qdrant", "qdrant_in_memory", "custom"]`
    - `config: dict | None = None`
  - Methods:
    - `validate_adapter()` (Pydantic `@model_validator(mode="after")`)
      - Ensures `config` is provided for non-`custom` adapters.
      - Validates `config` against the corresponding Pydantic schema for `qdrant` / `qdrant_in_memory`.
    - `load() -> IVectorStorePort`
      - Instantiates:
        - `QdrantAdapter(**config)` when `adapter == "qdrant"`
        - `QdrantInMemoryAdapter(**config)` when `adapter == "qdrant_in_memory"`
      - Delegates to `GenericLoader.load()` when `adapter == "custom"`.

- `VectorStoreServiceConfiguration` (Pydantic `BaseModel`)
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
  - `naas_abi_core.engine.engine_configuration.utils.PydanticModelValidator.pydantic_model_validator`
  - `naas_abi_core.services.vector_store.VectorStoreService`
  - `naas_abi_core.services.vector_store.IVectorStorePort`
- Adapter implementations are lazily imported at load time:
  - `naas_abi_core.services.vector_store.adapters.QdrantAdapter.QdrantAdapter`
  - `naas_abi_core.services.vector_store.adapters.QdrantInMemoryAdapter.QdrantInMemoryAdapter`

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

service = cfg.load()  # VectorStoreService with a loaded adapter
```

## Caveats
- For `adapter` values other than `"custom"`, `config` is required; missing `config` triggers an assertion error.
- `config` is validated for `"qdrant"` and `"qdrant_in_memory"`; unknown fields are rejected by the underlying Pydantic models (`extra="forbid"`).
- `"custom"` behavior depends on `GenericLoader.load()` (not defined in this file).
