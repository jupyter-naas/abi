from typing import Any, Literal

from naas_abi_core.engine.engine_configuration.EngineConfiguration_GenericLoader import (
    GenericLoader,
)
from naas_abi_core.engine.engine_configuration.utils.PydanticModelValidator import (
    pydantic_model_validator,
)
from naas_abi_core.services.document.DocumentPort import IDocumentAdapter
from naas_abi_core.services.document.DocumentService import DocumentService
from pydantic import BaseModel, ConfigDict, Field, model_validator


class DocumentAdapterSQLiteConfiguration(BaseModel):
    model_config = ConfigDict(extra="forbid", hide_input_in_errors=True)

    path: str = Field(default="storage/documents.sqlite", min_length=1)
    timeout: float = Field(default=5.0, gt=0, allow_inf_nan=False)


class DocumentAdapterPostgreSQLConfiguration(BaseModel):
    model_config = ConfigDict(extra="forbid", hide_input_in_errors=True)

    dsn: str = Field(min_length=1, repr=False)
    schema_name: str = Field(
        default="abi_document", alias="schema", pattern=r"^[a-z_][a-z0-9_]{0,62}$"
    )
    connect_timeout: int = Field(default=5, gt=0)
    statement_timeout: int = Field(default=30000, gt=0)
    pool_max_size: int = Field(default=10, ge=1)
    pool_timeout: float = Field(default=5.0, gt=0, allow_inf_nan=False)


class DocumentAdapterConfiguration(GenericLoader):
    model_config = ConfigDict(extra="forbid")
    adapter: Literal["sqlite", "postgresql", "custom"]
    config: dict[str, Any] = Field(default_factory=dict, repr=False)

    @model_validator(mode="after")
    def validate_adapter(self) -> "DocumentAdapterConfiguration":
        if self.adapter == "sqlite":
            pydantic_model_validator(
                DocumentAdapterSQLiteConfiguration,
                self.config,
                "Invalid configuration for services.document.document_adapter 'sqlite' adapter",
            )
        elif self.adapter == "postgresql":
            pydantic_model_validator(
                DocumentAdapterPostgreSQLConfiguration,
                self.config,
                "Invalid configuration for services.document.document_adapter 'postgresql' adapter",
            )
        elif (
            not self.python_module
            or not self.module_callable
            or self.custom_config is None
        ):
            raise ValueError(
                "custom adapters require python_module, module_callable and custom_config"
            )
        return self

    def load(self) -> IDocumentAdapter:
        if self.adapter == "sqlite":
            from naas_abi_core.services.document.adapters.secondary.DocumentSecondaryAdapterSQLite import (
                DocumentSecondaryAdapterSQLite,
            )

            return DocumentSecondaryAdapterSQLite(
                **DocumentAdapterSQLiteConfiguration.model_validate(
                    self.config
                ).model_dump()
            )
        if self.adapter == "postgresql":
            from naas_abi_core.services.document.adapters.secondary.DocumentSecondaryAdapterPostgreSQL import (
                DocumentSecondaryAdapterPostgreSQL,
            )

            return DocumentSecondaryAdapterPostgreSQL(
                **DocumentAdapterPostgreSQLConfiguration.model_validate(
                    self.config
                ).model_dump(by_alias=True)
            )
        adapter = super().load()
        if not isinstance(adapter, IDocumentAdapter):
            raise TypeError("Custom document adapter must implement IDocumentAdapter")
        return adapter


class DocumentServiceConfiguration(BaseModel):
    document_adapter: DocumentAdapterConfiguration = Field(
        default_factory=lambda: DocumentAdapterConfiguration(adapter="sqlite")
    )

    def load(self) -> DocumentService:
        # Module proxies bind the module's full dotted name at the composition root.
        return DocumentService._for_engine(self.document_adapter.load())
