# EngineConfiguration_BusService

## What it is
Configuration models and loaders for constructing a `BusService` with a selectable bus adapter (`rabbitmq`, `python_queue`, or `custom`). Uses Pydantic validation to enforce adapter-specific configuration rules.

## Public API
- `class BusAdapterRabbitMQConfiguration(BaseModel)`
  - Validates RabbitMQ adapter configuration.
  - Fields:
    - `rabbitmq_url: str` (default: `"amqp://abi:abi@127.0.0.1:5672"`)
- `class BusAdapterPythonQueueConfiguration(BaseModel)`
  - Validates Python queue adapter configuration (no fields; config may be empty).
- `class BusAdapterConfiguration(GenericLoader)`
  - Selects and loads an `IBusAdapter` implementation based on `adapter`.
  - Fields:
    - `adapter: Literal["rabbitmq", "python_queue", "custom"]`
    - `config: dict | None` (adapter-specific)
  - Methods:
    - `validate_adapter(self) -> BusAdapterConfiguration` (Pydantic `@model_validator`)
      - Enforces:
        - `config` is required when `adapter != "custom"`.
        - RabbitMQ config must match `BusAdapterRabbitMQConfiguration`.
        - Python queue adapter accepts no config; if provided, it must match `BusAdapterPythonQueueConfiguration`.
    - `load(self) -> IBusAdapter`
      - `rabbitmq`: lazy-imports and returns `RabbitMQAdapter(**config)`
      - `python_queue`: lazy-imports and returns `PythonQueueAdapter()`
      - `custom`: delegates to `GenericLoader.load()`
      - otherwise raises `ValueError`
- `class BusServiceConfiguration(BaseModel)`
  - Fields:
    - `bus_adapter: BusAdapterConfiguration`
  - Methods:
    - `load(self) -> BusService`
      - Returns `BusService(adapter=self.bus_adapter.load())`

## Configuration/Dependencies
- Depends on:
  - `pydantic` (`BaseModel`, `ConfigDict`, `model_validator`)
  - `naas_abi_core.engine.engine_configuration.EngineConfiguration_GenericLoader.GenericLoader`
  - `naas_abi_core.engine.engine_configuration.utils.PydanticModelValidator.pydantic_model_validator`
  - `naas_abi_core.services.bus.BusPorts.IBusAdapter`
  - `naas_abi_core.services.bus.BusService.BusService`
- Adapter implementations are imported lazily during `BusAdapterConfiguration.load()`:
  - `naas_abi_core.services.bus.adapters.secondary.RabbitMQAdapter.RabbitMQAdapter`
  - `naas_abi_core.services.bus.adapters.secondary.PythonQueueAdapter.PythonQueueAdapter`

## Usage
```python
from naas_abi_core.engine.engine_configuration.EngineConfiguration_BusService import (
    BusServiceConfiguration, BusAdapterConfiguration
)

cfg = BusServiceConfiguration(
    bus_adapter=BusAdapterConfiguration(
        adapter="python_queue",
        config={},  # optional; if provided must be valid (empty is allowed)
    )
)

bus_service = cfg.load()
```

RabbitMQ example:
```python
from naas_abi_core.engine.engine_configuration.EngineConfiguration_BusService import (
    BusServiceConfiguration, BusAdapterConfiguration
)

cfg = BusServiceConfiguration(
    bus_adapter=BusAdapterConfiguration(
        adapter="rabbitmq",
        config={"rabbitmq_url": "amqp://abi:abi@127.0.0.1:5672"},
    )
)

bus_service = cfg.load()
```

## Caveats
- `config` is required for `adapter="rabbitmq"` and generally required for all non-`custom` adapters (per validator).
- Extra keys in adapter configs are forbidden (`extra="forbid"`); unknown fields will fail validation.
- `adapter="custom"` relies on `GenericLoader.load()` behavior (not defined in this file).
