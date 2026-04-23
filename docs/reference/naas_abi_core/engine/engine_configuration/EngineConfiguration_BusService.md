# EngineConfiguration_BusService

## What it is
Configuration models and loaders for wiring a `BusService` with a selectable bus adapter (`rabbitmq`, `python_queue`, or `custom`). Built on Pydantic for validation and a generic loader mechanism for custom adapters.

## Public API

- `BusAdapterRabbitMQConfiguration (pydantic.BaseModel)`
  - Purpose: Validates configuration for the RabbitMQ bus adapter.
  - Fields:
    - `rabbitmq_url: str` (default: `"amqp://abi:abi@127.0.0.1:5672"`)
  - Notes: Extra keys are forbidden (`extra="forbid"`).

- `BusAdapterPythonQueueConfiguration (pydantic.BaseModel)`
  - Purpose: Validates configuration for the Python-queue bus adapter.
  - Fields:
    - `persistence_path: str | None` (default: `None`)
    - `journal_mode: Literal["DELETE","TRUNCATE","PERSIST","MEMORY","WAL","OFF"]` (default: `"WAL"`)
    - `busy_timeout_ms: int` (default: `5000`)
    - `poll_interval_seconds: float` (default: `0.05`)
    - `lock_timeout_seconds: float` (default: `1.0`)
  - Notes: Extra keys are forbidden (`extra="forbid"`).

- `BusAdapterConfiguration (GenericLoader)`
  - Purpose: Selects and validates an adapter configuration; can also load a custom adapter via `GenericLoader`.
  - Fields:
    - `adapter: Literal["rabbitmq", "python_queue", "custom"]`
    - `config: dict | None` (default: `None`)
  - Methods:
    - `validate_adapter() -> BusAdapterConfiguration`
      - Validates `config` against the appropriate Pydantic model.
      - Enforces `config is not None` when `adapter != "custom"`.
      - For `python_queue`, validation only occurs if `config` is provided.
    - `load() -> IBusAdapter`
      - `rabbitmq`: lazy-imports and returns `RabbitMQAdapter(**config)`
      - `python_queue`: lazy-imports and returns `PythonQueueAdapter(**config)` (requires `config` not `None`)
      - `custom`: delegates to `GenericLoader.load()`
      - Otherwise: raises `ValueError`

- `BusServiceConfiguration (pydantic.BaseModel)`
  - Purpose: Top-level configuration for constructing a `BusService`.
  - Fields:
    - `bus_adapter: BusAdapterConfiguration`
  - Methods:
    - `load() -> BusService`: returns `BusService(adapter=self.bus_adapter.load())`

## Configuration/Dependencies
- Depends on:
  - `pydantic` (`BaseModel`, `model_validator`, `ConfigDict`)
  - `naas_abi_core.engine.engine_configuration.EngineConfiguration_GenericLoader.GenericLoader` (for `custom` adapter loading)
  - `naas_abi_core.engine.engine_configuration.utils.PydanticModelValidator.pydantic_model_validator`
  - `naas_abi_core.services.bus.BusService.BusService`
  - `naas_abi_core.services.bus.BusPorts.IBusAdapter`
- Adapter implementations are imported lazily during `BusAdapterConfiguration.load()`:
  - `RabbitMQAdapter` from `naas_abi_core.services.bus.adapters.secondary.RabbitMQAdapter`
  - `PythonQueueAdapter` from `naas_abi_core.services.bus.adapters.secondary.PythonQueueAdapter`

## Usage

```python
from naas_abi_core.engine.engine_configuration.EngineConfiguration_BusService import (
    BusServiceConfiguration,
)

cfg = BusServiceConfiguration(
    bus_adapter={
        "adapter": "rabbitmq",
        "config": {"rabbitmq_url": "amqp://abi:abi@127.0.0.1:5672"},
    }
)

bus_service = cfg.load()
```

## Caveats
- `bus_adapter.config` is required for any adapter other than `"custom"`.
- Despite comments stating the Python queue adapter “doesn't require configuration”, `load()` asserts that `config` is not `None` for `"python_queue"`. If you use `"python_queue"`, pass at least an empty dict: `config={}`.
- Configuration models forbid unknown keys (`extra="forbid"`); extra fields will fail validation.
