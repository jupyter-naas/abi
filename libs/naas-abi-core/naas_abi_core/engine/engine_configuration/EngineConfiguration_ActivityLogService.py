from typing import Literal

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


class ActivityLogAdapterConfiguration(GenericLoader):
    adapter: Literal["sqlite", "custom"]
    config: dict | None = None

    @model_validator(mode="after")
    def validate_adapter(self) -> "ActivityLogAdapterConfiguration":
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

                return ActivityLogSqliteAdapter(**self.config)
            else:
                raise ValueError(f"Unknown adapter: {self.adapter}")
        else:
            return super().load()


class ActivityLogServiceConfiguration(BaseModel):
    activity_log_adapter: ActivityLogAdapterConfiguration

    def load(self) -> ActivityLogService:
        return ActivityLogService(adapter=self.activity_log_adapter.load())
