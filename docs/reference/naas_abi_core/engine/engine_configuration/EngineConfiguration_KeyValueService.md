# EngineConfiguration_KeyValueService

## What it is
Pydantic-based configuration models and loader logic for creating a `KeyValueService` with a selectable key-value adapter (`redis`, `python`, or `custom`).

## Public API
- `KeyValueAdapterRedisConfiguration` (Pydantic model)
  - Purpose: Validate configuration for the Redis KV adapter.
  - Fields:
    - `redis_url: str` (default: `"redis://localhost:6379"`)
- `KeyValueAdapterPythonConfiguration` (Pydantic model)
  - Purpose: Validate configuration for the Python KV adapter.
  - Fields: none (extra fields are forbidden).
- `KeyValueAdapterConfiguration` (`GenericLoader`)
  - Purpose: Select and load a KV adapter implementation based on `adapter`.
  - Fields:
    - `adapter: Literal["redis", "python", "custom"]`
    - `config: dict | None`
  - Methods:
    - `validate_adapter(self) -> KeyValueAdapterConfiguration`: Pydantic `@model_validator` that enforces required config and validates it against the adapter-specific schema.
    - `load(self) -> IKeyValueAdapter`: Instantiates and returns the configured adapter, or delegates to `GenericLoader.load()` for `custom`.
- `KeyValueServiceConfiguration` (Pydantic model)
  - Purpose: Top-level configuration that loads a `KeyValueService`.
  - Fields:
    - `kv_adapter: KeyValueAdapterConfiguration`
  - Methods:
    - `load(self) -> KeyValueService`: Constructs `KeyValueService(adapter=...)`.

## Configuration/Dependencies
- Depends on:
  - `pydantic` (`BaseModel`, `ConfigDict`, `model_validator`)
  - `naas_abi_core.engine.engine_configuration.EngineConfiguration_GenericLoader.GenericLoader`
  - `naas_abi_core.engine.engine_configuration.utils.PydanticModelValidator.pydantic_model_validator`
  - `naas_abi_core.services.keyvalue.KeyValueService`
  - `naas_abi_core.services.keyvalue.KeyValuePorts.IKeyValueAdapter`
- Adapter implementations are imported lazily during `KeyValueAdapterConfiguration.load()`:
  - Redis: `naas_abi_core.services.keyvalue.adapters.secondary.RedisAdapter.RedisAdapter`
  - Python: `naas_abi_core.services.keyvalue.adapters.secondary.PythonAdapter.PythonAdapter`
- Pydantic models in this module set `extra="forbid"` for adapter config schemas (unknown fields are rejected).

## Usage
```python
from naas_abi_core.engine.engine_configuration.EngineConfiguration_KeyValueService import (
    KeyValueServiceConfiguration,
)

cfg = KeyValueServiceConfiguration.model_validate(
    {
        "kv_adapter": {
            "adapter": "redis",
            "config": {"redis_url": "redis://localhost:6379"},
        }
    }
)

kv_service = cfg.load()  # KeyValueService instance configured with RedisAdapter
```

## Caveats
- For `adapter` values other than `"custom"`, `config` is required; missing config triggers an `AssertionError`.
- For `"redis"` and `"python"`, `config` is validated against adapter-specific Pydantic schemas; invalid or extra fields are rejected.
- If `adapter` is `"custom"`, loading is delegated to `GenericLoader.load()`; the required shape/behavior depends on `GenericLoader` implementation (not defined here).
