from typing import Literal, Self

from naas_abi_core.engine.engine_configuration.EngineConfiguration_GenericLoader import (
    GenericLoader,
)
from naas_abi_core.engine.engine_configuration.utils.PydanticModelValidator import (
    pydantic_model_validator,
)
from naas_abi_core.services.activity_log.ActivityLogPort import IActivityLogAdapter
from naas_abi_core.services.activity_log.ActivityLogService import ActivityLogService
from pydantic import BaseModel, ConfigDict, model_validator


class ActivityLogAdapterSqliteConfiguration(BaseModel):
    """SQLite-backed activity log adapter configuration.

    activity_log_adapter:
      adapter: "sqlite"
      config:
        data_dir: "storage/activity_log"
        synchronous: "NORMAL"
        journal_mode: "WAL"
        max_open_connections: 200
        busy_timeout_ms: 5000
    """

    model_config = ConfigDict(extra="forbid")

    data_dir: str = "storage/activity_log"
    synchronous: Literal["FULL", "NORMAL", "OFF"] = "NORMAL"
    journal_mode: Literal["WAL", "DELETE", "TRUNCATE", "PERSIST", "MEMORY", "OFF"] = (
        "WAL"
    )
    max_open_connections: int = 200
    busy_timeout_ms: int = 5000


class ActivityLogAdapterNATSConfiguration(BaseModel):
    """Activity log adapter NATS RPC client configuration.

    Talks to a remote ``ActivityLogPrimaryAdapterNATS`` over NATS
    request/reply -- see docs/specs/rfcs/20260910_distributed-modules-nats-jetstream.md
    (Stage 1) and naas_abi_core/proto/activity_log/v1/activity_log.proto.

    activity_log_adapter:
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


class ActivityLogAdapterConfiguration(GenericLoader):
    adapter: Literal["sqlite", "nats_rpc", "custom"]
    config: (
        ActivityLogAdapterSqliteConfiguration | ActivityLogAdapterNATSConfiguration
        | None
    ) = None

    @model_validator(mode="after")
    def validate_adapter(self) -> Self:
        if self.adapter != "custom":
            assert self.config is not None, (
                "config is required if adapter is not custom"
            )

        if self.adapter == "sqlite":
            pydantic_model_validator(
                ActivityLogAdapterSqliteConfiguration,
                self.config,
                "Invalid configuration for services.activity_log.activity_log_adapter 'sqlite' adapter",
            )
        if self.adapter == "nats_rpc":
            pydantic_model_validator(
                ActivityLogAdapterNATSConfiguration,
                self.config,
                "Invalid configuration for services.activity_log.activity_log_adapter 'nats_rpc' adapter",
            )

        return self

    def load(self) -> IActivityLogAdapter:
        if self.adapter != "custom":
            assert self.config is not None, (
                "config is required if adapter is not custom"
            )

            if self.adapter == "sqlite":
                from naas_abi_core.services.activity_log.adapters.secondary.ActivityLogSqliteAdapter import (
                    ActivityLogSqliteAdapter,
                )

                return ActivityLogSqliteAdapter(**self.config.model_dump())
            elif self.adapter == "nats_rpc":
                from naas_abi_core.services.activity_log.adapters.secondary.ActivityLogSecondaryAdapterNATSClient import (
                    ActivityLogSecondaryAdapterNATSClient,
                )

                return ActivityLogSecondaryAdapterNATSClient(
                    **self.config.model_dump()
                )
            else:
                raise ValueError(f"Unknown adapter: {self.adapter}")
        else:
            return super().load()


class ActivityLogServiceConfiguration(BaseModel):
    activity_log_adapter: ActivityLogAdapterConfiguration

    def load(self) -> ActivityLogService:
        return ActivityLogService(adapter=self.activity_log_adapter.load())
