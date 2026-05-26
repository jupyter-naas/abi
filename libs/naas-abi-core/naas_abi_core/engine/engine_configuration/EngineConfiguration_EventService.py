from typing import Literal

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


class EventAdapterConfiguration(GenericLoader):
    adapter: Literal["sqlite", "custom"]
    config: dict | None = None

    @model_validator(mode="after")
    def validate_adapter(self) -> "EventAdapterConfiguration":
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

                return EventSQLiteAdapter(**self.config)
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
