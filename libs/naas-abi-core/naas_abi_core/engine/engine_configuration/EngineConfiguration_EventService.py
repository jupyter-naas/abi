from typing import Any, Literal, Self

from naas_abi_core.engine.engine_configuration.EngineConfiguration_GenericLoader import (
    GenericLoader,
    config_model,
)
from naas_abi_core.engine.engine_configuration.utils.PydanticModelValidator import (
    pydantic_model_validator,
)
from naas_abi_core.services.event.EventPort import IEventAdapter
from naas_abi_core.services.event.EventService import EventService
from pydantic import BaseModel, ConfigDict, Field, ValidationError, model_validator


class EventAdapterSqliteConfiguration(BaseModel):
    """SQLite-backed event log adapter configuration.

    event_adapter:
      adapter: "sqlite"
      config:
        db_path: "storage/events/events.sqlite"
    """

    model_config = ConfigDict(extra="forbid")

    db_path: str = "storage/events/events.sqlite"


class EventAdapterPostgreSQLConfiguration(BaseModel):
    """PostgreSQL event log, shared by every engine (deploys without downtime).

    event_adapter:
      adapter: "postgresql"
      config:
        dsn: "{{ secret.EVENT_POSTGRES_DSN }}"
        schema: "abi_event"
    """

    model_config = ConfigDict(extra="forbid", hide_input_in_errors=True)

    dsn: str = Field(min_length=1, repr=False)
    schema_name: str = Field(
        default="abi_event", alias="schema", pattern=r"^[a-z_][a-z0-9_]{0,62}$"
    )
    connect_timeout: int = Field(default=5, gt=0)
    statement_timeout: int = Field(default=30000, gt=0)
    pool_max_size: int = Field(default=10, ge=1)
    pool_timeout: float = Field(default=5.0, gt=0, allow_inf_nan=False)
    # Events older than this move to the Dataset Service (hourly job, NATS mode);
    # null keeps every event here.
    archive_after_days: float | None = Field(default=7, gt=0, allow_inf_nan=False)
    archive_batch_rows: int = Field(default=10_000, ge=1, le=100_000)


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
    adapter: Literal["sqlite", "postgresql", "nats_rpc", "custom"]
    config: (
        EventAdapterSqliteConfiguration
        | EventAdapterPostgreSQLConfiguration
        | EventAdapterNATSConfiguration
        | None
    ) = Field(default=None, repr=False)

    @model_validator(mode="before")
    @classmethod
    def _parse_postgresql_settings(cls, data: Any) -> Any:
        """PostgreSQL settings are parsed on their own, so an invalid one never
        echoes the DSN through the errors of the other config models."""
        if not (
            isinstance(data, dict)
            and data.get("adapter") == "postgresql"
            and isinstance(data.get("config"), dict)
        ):
            return data
        try:
            settings = EventAdapterPostgreSQLConfiguration.model_validate(
                data["config"]
            )
        except ValidationError as exc:
            problems = "; ".join(
                f"{'.'.join(str(p) for p in error['loc'])}: {error['msg']}"
                for error in exc.errors(include_input=False, include_url=False)
            )
            raise ValueError(
                "Invalid configuration for services.event.event_adapter "
                f"'postgresql' adapter: {problems}"
            ) from None
        return {**data, "config": settings}

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
        if self.adapter == "postgresql":
            pydantic_model_validator(
                EventAdapterPostgreSQLConfiguration,
                self.config,
                "Invalid configuration for services.event.event_adapter 'postgresql' adapter",
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
            elif self.adapter == "postgresql":
                from naas_abi_core.services.event.adapters.secondary import (
                    EventPostgreSQLAdapter as postgresql,
                )

                settings = config_model(
                    EventAdapterPostgreSQLConfiguration, self.config
                )
                return postgresql.EventPostgreSQLAdapter(
                    **settings.model_dump(by_alias=True)
                )
            elif self.adapter == "nats_rpc":
                from naas_abi_core.services.event.adapters.secondary.EventSecondaryAdapterNATSClient import (
                    EventSecondaryAdapterNATSClient,
                )

                return EventSecondaryAdapterNATSClient(**self.config.model_dump())
            else:
                raise ValueError(f"Unknown adapter: {self.adapter}")
        else:
            return super().load()

    def local_storage(self) -> str | None:
        """Where the events live (single-serving-engine ADR)."""
        if self.adapter == "sqlite":
            path = config_model(EventAdapterSqliteConfiguration, self.config).db_path
            return f"SQLite at {path}"
        if self.adapter == "custom":
            return self.custom_local_storage()
        return None  # postgresql; nats_rpc is another engine's


class EventServiceConfiguration(BaseModel):
    event_adapter: EventAdapterConfiguration

    def load(self) -> EventService:
        # Bus is wired post-construction via IEngine.Services.wire_services()
        # — EventService picks it up from `self.services.bus` lazily.
        return EventService(adapter=self.event_adapter.load())
