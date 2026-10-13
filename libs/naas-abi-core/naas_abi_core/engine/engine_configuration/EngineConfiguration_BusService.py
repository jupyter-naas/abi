from typing import Literal

from naas_abi_core.engine.engine_configuration.EngineConfiguration_GenericLoader import (
    GenericLoader,
)
from naas_abi_core.engine.engine_configuration.utils.PydanticModelValidator import (
    pydantic_model_validator,
)
from naas_abi_core.services.bus.BusPorts import IBusAdapter
from naas_abi_core.services.bus.BusService import BusService
from pydantic import BaseModel, ConfigDict, model_validator


class BusAdapterRabbitMQConfiguration(BaseModel):
    """RabbitMQ bus adapter configuration.

    bus_adapter:
      adapter: "rabbitmq"
      config:
        rabbitmq_url: "{{ secret.RABBITMQ_URL }}"
    """

    model_config = ConfigDict(extra="forbid")

    rabbitmq_url: str = "amqp://abi:abi@127.0.0.1:5672"


class BusAdapterPythonQueueConfiguration(BaseModel):
    """Python queue bus adapter configuration.

    bus_adapter:
      adapter: "python_queue"
      config: {}
    """

    model_config = ConfigDict(extra="forbid")

    persistence_path: str | None = None
    journal_mode: Literal["DELETE", "TRUNCATE", "PERSIST", "MEMORY", "WAL", "OFF"] = (
        "WAL"
    )
    busy_timeout_ms: int = 5000
    poll_interval_seconds: float = 0.05
    lock_timeout_seconds: float = 1.0


class BusAdapterNATSConfiguration(BaseModel):
    """NATS JetStream bus adapter configuration.

    Opt-in alongside "rabbitmq"/"python_queue", not a replacement yet — see
    docs/specs/rfcs/20260910_distributed-modules-nats-jetstream.md (Stage 1).

    bus_adapter:
      adapter: "nats_jetstream"
      config:
        nats_url: "nats://127.0.0.1:4222"
    """

    model_config = ConfigDict(extra="forbid")

    nats_url: str = "nats://127.0.0.1:4222"


class BusAdapterConfiguration(GenericLoader):
    adapter: Literal["rabbitmq", "python_queue", "nats_jetstream", "custom"]
    config: dict | None = None

    @model_validator(mode="after")
    def validate_adapter(self) -> "BusAdapterConfiguration":
        if self.adapter != "custom":
            assert self.config is not None, (
                "config is required if adapter is not custom"
            )

        if self.adapter == "rabbitmq":
            assert self.config is not None, "config is required for rabbitmq adapter"
            pydantic_model_validator(
                BusAdapterRabbitMQConfiguration,
                self.config,
                "Invalid configuration for services.bus.bus_adapter 'rabbitmq' adapter",
            )

        if self.adapter == "python_queue":
            # Python queue adapter doesn't require configuration
            if self.config is not None:
                pydantic_model_validator(
                    BusAdapterPythonQueueConfiguration,
                    self.config,
                    "Invalid configuration for services.bus.bus_adapter 'python_queue' adapter",
                )

        if self.adapter == "nats_jetstream":
            if self.config is not None:
                pydantic_model_validator(
                    BusAdapterNATSConfiguration,
                    self.config,
                    "Invalid configuration for services.bus.bus_adapter 'nats_jetstream' adapter",
                )

        return self

    def load(self) -> IBusAdapter:
        # Lazy import: only import when actually loading
        if self.adapter == "rabbitmq":
            assert self.config is not None, "config is required for rabbitmq adapter"
            from naas_abi_core.services.bus.adapters.secondary.RabbitMQAdapter import (
                RabbitMQAdapter,
            )

            return RabbitMQAdapter(**self.config)
        elif self.adapter == "python_queue":
            from naas_abi_core.services.bus.adapters.secondary.PythonQueueAdapter import (
                PythonQueueAdapter,
            )

            assert self.config is not None, (
                "config is required for python_queue adapter"
            )
            return PythonQueueAdapter(**self.config)
        elif self.adapter == "nats_jetstream":
            from naas_abi_core.services.bus.adapters.secondary.NATSJetStreamAdapter import (
                NATSJetStreamAdapter,
            )

            config = self.config or {}
            return NATSJetStreamAdapter(**config)
        elif self.adapter == "custom":
            return super().load()
        else:
            raise ValueError(f"Unknown adapter: {self.adapter}")


class BusServiceConfiguration(BaseModel):
    bus_adapter: BusAdapterConfiguration
    # Log a durable event for every message crossing the bus. Off by default:
    # it costs one event-log append per message, and engine boot alone
    # publishes one message per ontology triple. Turn on to debug bus traffic.
    emit_message_events: bool = False

    def load(self) -> BusService:
        return BusService(
            adapter=self.bus_adapter.load(),
            emit_message_events=self.emit_message_events,
        )
