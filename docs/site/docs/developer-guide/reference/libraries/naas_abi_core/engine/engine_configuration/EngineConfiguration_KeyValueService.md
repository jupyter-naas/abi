# EngineConfiguration_KeyValueService

## What it is
Pydantic configuration models and loader logic for constructing a `KeyValueService` with a selectable key-value adapter (`redis`, `python`, `nats_rpc`, or `custom`).

## Public API
- **`KeyValueAdapterRedisConfiguration` (`pydantic.BaseModel`)**
  - Validates configuration for the Redis adapter.
  - Fields:
    - `redis_url: str = "redis://localhost:6379"`
  - Notes: `extra="forbid"` (unknown keys rejected).

- **`KeyValueAdapterPythonConfiguration` (`pydantic.BaseModel`)**
  - Validates configuration for the Python adapter.
  - Fields:
    - `persistence_path: str | None = None`
    - `journal_mode: Literal["DELETE","TRUNCATE","PERSIST","MEMORY","WAL","OFF"] = "WAL"`
    - `busy_timeout_ms: int = 5000`
  - Notes: `extra="forbid"`.

- **`KeyValueAdapterNATSConfiguration` (`pydantic.BaseModel`)**
  - Validates configuration for the NATS RPC client adapter.
  - Fields:
    - `nats_url: str = "nats://127.0.0.1:4222"`
    - `jwt_secret: str`
    - `service_identity: str = "api"`
  - Notes: `extra="forbid"`.

- **`KeyValueAdapterConfiguration` (`GenericLoader`)**
  - Selects and loads an `IKeyValueAdapter`.
  - Fields:
    - `adapter: Literal["redis", "python", "nats_rpc", "custom"]`
    - `config: dict | None = None`
  - Methods:
    - `validate_adapter() -> KeyValueAdapterConfiguration` (Pydantic `@model_validator(mode="after")`)
      - Requires `config` for all non-`custom` adapters.
      - Validates `config` against the corresponding Pydantic config model.
    - `load() -> IKeyValueAdapter`
      - Lazily imports and instantiates:
        - `RedisAdapter(**config)` for `adapter="redis"`
        - `PythonAdapter(**config)` for `adapter="python"`
        - `KeyValueSecondaryAdapterNATSClient(**config)` for `adapter="nats_rpc"`
      - Uses `GenericLoader.load()` for `adapter="custom"`.
    - `local_storage() -> str | None`
      - Returns a human-readable description of where keys live:
        - For `python`: `"this process"` or `"this process, persisted to {path}"`
        - For `custom`: delegates to `self.custom_local_storage()`
        - Otherwise: `None`

- **`KeyValueServiceConfiguration` (`pydantic.BaseModel`)**
  - Fields:
    - `kv_adapter: KeyValueAdapterConfiguration`
  - Methods:
    - `load() -> KeyValueService` — constructs `KeyValueService(adapter=kv_adapter.load())`.

## Configuration/Dependencies
- **Pydantic**: validation via `BaseModel`, `ConfigDict(extra="forbid")`, and `@model_validator`.
- **GenericLoader framework**:
  - `KeyValueAdapterConfiguration` extends `GenericLoader`.
  - Uses `config_model(...)` to parse `python` adapter config for `local_storage()`.
- **Lazy-loaded adapter implementations**:
  - `naas_abi_core.services.keyvalue.adapters.secondary.RedisAdapter.RedisAdapter`
  - `naas_abi_core.services.keyvalue.adapters.secondary.PythonAdapter.PythonAdapter`
  - `naas_abi_core.services.keyvalue.adapters.secondary.KeyValueSecondaryAdapterNATSClient.KeyValueSecondaryAdapterNATSClient`

## Usage
```python
from naas_abi_core.engine.engine_configuration.EngineConfiguration_KeyValueService import (
    KeyValueServiceConfiguration,
    KeyValueAdapterConfiguration,
)

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

cfg = KeyValueServiceConfiguration(
    kv_adapter=KeyValueAdapterConfiguration(
        adapter="nats_rpc",
        config={
            "nats_url": "nats://127.0.0.1:4222",
            "jwt_secret": "super-secret",
            "service_identity": "api",
        },
    )
)

service = cfg.load()
```

## Caveats
- `config` is required for `adapter in {"redis","python","nats_rpc"}` (asserted in validation and in `load()`).
- Adapter-specific config models reject unknown keys (`extra="forbid"`).
- `load()` raises `ValueError` for unknown non-`custom` adapter values.
