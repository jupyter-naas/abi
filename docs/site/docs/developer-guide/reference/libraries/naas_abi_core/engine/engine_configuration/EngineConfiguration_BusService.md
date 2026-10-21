# EngineConfiguration_BusService

## What it is
Pydantic configuration models and a loader for creating a `BusService` wired to a selectable bus adapter (`rabbitmq`, `python_queue`, `nats_jetstream`, or `custom`). Includes validation of adapter-specific config and lazy imports of adapter implementations.

## Public API

- `BusAdapterRabbitMQConfiguration (pydantic.BaseModel)`
  - Purpose: Validate config for the RabbitMQ bus adapter.
  - Fields:
    - `rabbitmq_url: str` (default: `"amqp://abi:abi@127.0.0.1:5672"`)
  - Notes: Unknown keys are rejected (`extra="forbid"`).

- `BusAdapterPythonQueueConfiguration (pydantic.BaseModel)`
  - Purpose: Validate config for the Python queue bus adapter.
  - Fields:
    - `persistence_path: str | None` (default: `None`)
    - `journal_mode: Literal["DELETE","TRUNCATE","PERSIST","MEMORY","WAL","OFF"]` (default: `"WAL"`)
    - `busy_timeout_ms: int` (default: `5000`)
    - `poll_interval_seconds: float` (default: `0.05`)
    - `lock_timeout_seconds: float` (default: `1.0`)
  - Notes: Unknown keys are rejected (`extra="forbid"`).

- `BusAdapterNATSConfiguration (pydantic.BaseModel)`
  - Purpose: Validate config for the NATS JetStream bus adapter.
  - Fields:
    - `nats_url: str` (default: `"nats://127.0.0.1:4222"`)
  - Notes: Unknown keys are rejected (`extra="forbid"`).

- `BusAdapterConfiguration (GenericLoader)`
  - Purpose: Select, validate, and load an `IBusAdapter` implementation.
  - Fields:
    - `adapter: Literal["rabbitmq", "python_queue", "nats_jetstream", "custom"]`
    - `config: dict | None` (default: `None`)
  - Methods:
    - `validate_adapter() -> BusAdapterConfiguration`
      - Enforces `config is not None` when `adapter != "custom"`.
      - Validates `config` against the adapter’s Pydantic model:
        - `rabbitmq`: always validates and requires `config`
        - `python_queue`: validates only if `config` is not `None` (but see caveat)
        - `nats_jetstream`: validates only if `config` is not `None`
    - `load() -> IBusAdapter`
      - `rabbitmq`: returns `RabbitMQAdapter(**config)` (requires `config`)
      - `python_queue`: returns `PythonQueueAdapter(**config)` (requires `config`)
      - `nats_jetstream`: returns `NATSJetStreamAdapter(**(config or {}))`
      - `custom`: delegates to `GenericLoader.load()`
      - otherwise: raises `ValueError`

- `BusServiceConfiguration (pydantic.BaseModel)`
  - Purpose: Top-level configuration for constructing a `BusService`.
  - Fields:
    - `bus_adapter: BusAdapterConfiguration`
    - `emit_message_events: bool` (default: `False`) — if enabled, emits a durable event per bus message.
  - Methods:
    - `load() -> BusService`: returns `BusService(adapter=..., emit_message_events=...)`

## Configuration/Dependencies
- Depends on:
  - `pydantic` (`BaseModel`, `ConfigDict`, `model_validator`)
  - `GenericLoader` (`naas_abi_core.engine.engine_configuration.EngineConfiguration_GenericLoader`)
  - `pydantic_model_validator` utility (`naas_abi_core.engine.engine_configuration.utils.PydanticModelValidator`)
  - `BusService` (`naas_abi_core.services.bus.BusService`)
  - `IBusAdapter` (`naas_abi_core.services.bus.BusPorts`)
- Lazy-loaded adapter implementations (imported only in `BusAdapterConfiguration.load()`):
  - `RabbitMQAdapter` from `naas_abi_core.services.bus.adapters.secondary.RabbitMQAdapter`
  - `PythonQueueAdapter` from `naas_abi_core.services.bus.adapters.secondary.PythonQueueAdapter`
  - `NATSJetStreamAdapter` from `naas_abi_core.services.bus.adapters.secondary.NATSJetStreamAdapter`

## Usage

```python
from naas_abi_core.engine.engine_configuration.EngineConfiguration_BusService import (
    BusServiceConfiguration,
)

cfg = BusServiceConfiguration(
    bus_adapter={
        "adapter": "nats_jetstream",
        "config": {"nats_url": "nats://127.0.0.1:4222"},
    },
    emit_message_events=False,
)

bus_service = cfg.load()
```

## Caveats
- `bus_adapter.config` is required for any adapter other than `"custom"` (enforced by `assert` in validation).
- `python_queue` is commented as “doesn't require configuration”, but `load()` asserts `config is not None`. Provide at least `{}`:
  - `{"adapter": "python_queue", "config": {}}`
- Adapter configuration models use `extra="forbid"`; unknown keys will fail validation.
