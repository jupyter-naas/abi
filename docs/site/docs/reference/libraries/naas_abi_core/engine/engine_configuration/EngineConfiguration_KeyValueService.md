# EngineConfiguration_KeyValueService

## What it is
Configuration models and loader logic for constructing a `KeyValueService` with a pluggable key-value adapter (`redis`, `python`, or `custom`), using Pydantic validation.

## Public API
- **`KeyValueAdapterRedisConfiguration` (pydantic `BaseModel`)**
  - Validates configuration for the Redis adapter.
  - Fields:
    - `redis_url: str` (default: `"redis://localhost:6379"`)
- **`KeyValueAdapterPythonConfiguration` (pydantic `BaseModel`)**
  - Validates configuration for the Python adapter.
  - Fields:
    - `persistence_path: str | None` (default: `None`)
    - `journal_mode: Literal["DELETE","TRUNCATE","PERSIST","MEMORY","WAL","OFF"]` (default: `"WAL"`)
    - `busy_timeout_ms: int` (default: `5000`)
- **`KeyValueAdapterConfiguration` (`GenericLoader`)**
  - Selects an adapter type and validates/loads the corresponding adapter implementation.
  - Attributes:
    - `adapter: Literal["redis", "python", "custom"]`
    - `config: dict | None`
  - Methods:
    - `validate_adapter() -> KeyValueAdapterConfiguration` (Pydantic `@model_validator(mode="after")`)
      - Enforces `config` presence unless `adapter == "custom"`.
      - Validates `config` shape for `redis`/`python` via `pydantic_model_validator`.
    - `load() -> IKeyValueAdapter`
      - Lazily imports and instantiates:
        - `RedisAdapter(**config)` when `adapter == "redis"`
        - `PythonAdapter(**config)` when `adapter == "python"`
      - Delegates to `GenericLoader.load()` when `adapter == "custom"`.
- **`KeyValueServiceConfiguration` (pydantic `BaseModel`)**
  - Wraps adapter configuration and constructs the `KeyValueService`.
  - Attributes:
    - `kv_adapter: KeyValueAdapterConfiguration`
  - Methods:
    - `load() -> KeyValueService` — returns `KeyValueService(adapter=kv_adapter.load())`.

## Configuration/Dependencies
- **Pydantic** is used for schema validation; models use `extra="forbid"` for adapter-specific configs.
- Adapter implementations are imported lazily from:
  - `naas_abi_core.services.keyvalue.adapters.secondary.RedisAdapter.RedisAdapter`
  - `naas_abi_core.services.keyvalue.adapters.secondary.PythonAdapter.PythonAdapter`
- `custom` adapter path relies on `GenericLoader` behavior (not defined in this file).

## Usage
```python
from naas_abi_core.engine.engine_configuration.EngineConfiguration_KeyValueService import (
    KeyValueServiceConfiguration,
    KeyValueAdapterConfiguration,
)

# Redis-backed KeyValueService
cfg = KeyValueServiceConfiguration(
    kv_adapter=KeyValueAdapterConfiguration(
        adapter="redis",
        config={"redis_url": "redis://localhost:6379"},
    )
)

service = cfg.load()
```

```python
from naas_abi_core.engine.engine_configuration.EngineConfiguration_KeyValueService import (
    KeyValueServiceConfiguration,
    KeyValueAdapterConfiguration,
)

# Python-backed KeyValueService
cfg = KeyValueServiceConfiguration(
    kv_adapter=KeyValueAdapterConfiguration(
        adapter="python",
        config={
            "persistence_path": None,
            "journal_mode": "WAL",
            "busy_timeout_ms": 5000,
        },
    )
)

service = cfg.load()
```

## Caveats
- `config` is required for `adapter="redis"` and `adapter="python"`; it may be omitted only for `adapter="custom"`.
- For adapter-specific config models, unknown keys are rejected (`extra="forbid"`).
- `load()` raises `ValueError` for unknown non-custom adapter values.
