from typing import Literal, Self

from naas_abi_core.engine.engine_configuration.EngineConfiguration_GenericLoader import (
    GenericLoader,
)
from naas_abi_core.engine.engine_configuration.utils.PydanticModelValidator import (
    pydantic_model_validator,
)
from naas_abi_core.services.event.EventPort import IEventAdapter
from naas_abi_core.services.event.EventService import EventService
from pydantic import BaseModel, ConfigDict, model_validator


class EventAdapterSqliteConfiguration(BaseModel):
    """SQLite-backed event log adapter configuration.

    event_adapter:
      adapter: "sqlite"
      config:
        db_path: "storage/events/events.sqlite"
    """

    model_config = ConfigDict(extra="forbid")

    db_path: str = "storage/events/events.sqlite"


class EventAdapterNATSConfiguration(BaseModel):
    """Event adapter NATS RPC client configuration.

    Talks to a remote ``EventPrimaryAdapterNATS`` over NATS request/reply --
    see docs/specs/rfcs/20260910_distributed-modules-nats-jetstream.md
    (Stage 1) and naas_abi_core/proto/event/v1/event.proto. Only the six
    ``IEventAdapter`` methods are remoted this way; the bus-backed parts of
    ``EventService`` (``publish``'s broadcast, ``subscribe``) keep running
    100% locally wherever this configuration is loaded -- see
    naas_abi_core/services/event/adapters/event_nats_contract.py for the
    scope note.

    event_adapter:
      adapter: "nats_rpc"
      config:
        nats_url: "nats://127.0.0.1:4222"
        jwt_secret: "{{ secret.NATS_SERVICE_JWT_SECRET }}"
        service_identity: "api"
    """

    model_config = ConfigDict(extra="forbid")

    nats_url: str = "nats://127.0.0.1:4222"
    jwt_secret: str
    service_identity: str = "api"


class EventAdapterConfiguration(GenericLoader):
    adapter: Literal["sqlite", "nats_rpc", "custom"]
    config: EventAdapterSqliteConfiguration | EventAdapterNATSConfiguration | None = None

    @model_validator(mode="after")
    def validate_adapter(self) -> Self:
        if self.adapter != "custom":
            assert self.config is not None, (
                "config is required if adapter is not custom"
            )

        if self.adapter == "sqlite":
            pydantic_model_validator(
                EventAdapterSqliteConfiguration,
                self.config,
                "Invalid configuration for services.event.event_adapter 'sqlite' adapter",
            )
        if self.adapter == "nats_rpc":
            pydantic_model_validator(
                EventAdapterNATSConfiguration,
                self.config,
                "Invalid configuration for services.event.event_adapter 'nats_rpc' adapter",
            )

        return self

    def load(self) -> IEventAdapter:
        if self.adapter != "custom":
            assert self.config is not None, (
                "config is required if adapter is not custom"
            )

            if self.adapter == "sqlite":
                from naas_abi_core.services.event.adapters.secondary.EventSQLiteAdapter import (
                    EventSQLiteAdapter,
                )

                return EventSQLiteAdapter(**self.config.model_dump())
            elif self.adapter == "nats_rpc":
                from naas_abi_core.services.event.adapters.secondary.EventSecondaryAdapterNATSClient import (
                    EventSecondaryAdapterNATSClient,
                )

                return EventSecondaryAdapterNATSClient(**self.config.model_dump())
            else:
                raise ValueError(f"Unknown adapter: {self.adapter}")
        else:
            return super().load()


class EventServiceConfiguration(BaseModel):
    event_adapter: EventAdapterConfiguration

    def load(self) -> EventService:
        # Bus is wired post-construction via IEngine.Services.wire_services()
        # — EventService picks it up from `self.services.bus` lazily.
        return EventService(adapter=self.event_adapter.load())
