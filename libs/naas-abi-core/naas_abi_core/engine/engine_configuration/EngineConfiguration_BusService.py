from typing import Literal

from naas_abi_core.engine.engine_configuration.EngineConfiguration_GenericLoader import \
    GenericLoader
from naas_abi_core.engine.engine_configuration.utils.PydanticModelValidator import \
    pydantic_model_validator
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

    pass

class BusAdapterConfiguration(GenericLoader):
    adapter: Literal["rabbitmq", "python_queue", "custom"]
    config: dict | None = None

    @model_validator(mode="after")
    def validate_adapter(self) -> "BusAdapterConfiguration":
        if self.adapter != "custom":
            assert self.config is not None, (
                "config is required if adapter is not custom"
            )
        
        if self.adapter == "rabbitmq":
            assert self.config is not None, (
                "config is required for rabbitmq adapter"
            )
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

        return self

    def load(self) -> IBusAdapter:
        # Lazy import: only import when actually loading
        if self.adapter == "rabbitmq":
            assert self.config is not None, "config is required for rabbitmq adapter"
            from naas_abi_core.services.bus.adapters.secondary.RabbitMQAdapter import \
                RabbitMQAdapter

            return RabbitMQAdapter(**self.config)
        elif self.adapter == "python_queue":
            from naas_abi_core.services.bus.adapters.secondary.PythonQueueAdapter import \
                PythonQueueAdapter

            return PythonQueueAdapter()
        elif self.adapter == "custom":
            return super().load()
        else:
            raise ValueError(f"Unknown adapter: {self.adapter}")


class BusServiceConfiguration(BaseModel):
    bus_adapter: BusAdapterConfiguration

    def load(self) -> BusService:
        return BusService(adapter=self.bus_adapter.load())
