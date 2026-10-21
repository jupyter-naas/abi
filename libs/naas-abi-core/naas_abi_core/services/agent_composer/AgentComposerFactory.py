from __future__ import annotations

from collections.abc import Iterable, Mapping
from pathlib import Path
from typing import TYPE_CHECKING, Any

from naas_abi_core.services.agent_composer.adapters.secondary.DocumentAgentSpecRepositoryAdapter import (
    DocumentAgentSpecRepositoryAdapter,
)
from naas_abi_core.services.agent_composer.adapters.secondary.FileSystemAgentSpecRepositoryAdapter import (
    FileSystemAgentSpecRepositoryAdapter,
)
from naas_abi_core.services.agent_composer.adapters.secondary.InMemoryAgentSpecRepositoryAdapter import (
    InMemoryAgentSpecRepositoryAdapter,
)
from naas_abi_core.services.agent_composer.adapters.secondary.MappingSecretResolverAdapter import (
    MappingSecretResolverAdapter,
)
from naas_abi_core.services.agent_composer.adapters.secondary.SecretServiceResolverAdapter import (
    SecretServiceResolverAdapter,
)
from naas_abi_core.services.agent_composer.AgentComposerPort import (
    AgentSpec,
    IAgentSpecRepository,
    ISecretResolverPort,
)
from naas_abi_core.services.agent_composer.AgentComposerService import (
    AgentComposerService,
)
from naas_abi_core.services.model_registry.ModelRegistryPort import IModelRegistry
from naas_abi_core.services.tool_registry.ToolRegistryPort import IToolRegistry

if TYPE_CHECKING:
    from naas_abi_core.engine.IEngine import IEngine
    from naas_abi_core.services.document.DocumentService import DocumentService


class AgentComposerFactory:
    @staticmethod
    def InMemory(
        tool_registry: IToolRegistry,
        model_registry: IModelRegistry,
        specs: Iterable[AgentSpec] = (),
        secrets: Mapping[str, str] | None = None,
    ) -> AgentComposerService:
        return AgentComposerService(
            tool_registry=tool_registry,
            model_registry=model_registry,
            spec_repository=InMemoryAgentSpecRepositoryAdapter(specs),
            secret_resolver=MappingSecretResolverAdapter(secrets or {}),
        )

    @staticmethod
    def FileSystem(
        tool_registry: IToolRegistry,
        model_registry: IModelRegistry,
        directory: str | Path,
        secret_resolver: ISecretResolverPort | None = None,
    ) -> AgentComposerService:
        return AgentComposerService(
            tool_registry=tool_registry,
            model_registry=model_registry,
            spec_repository=FileSystemAgentSpecRepositoryAdapter(directory),
            secret_resolver=secret_resolver,
        )

    @staticmethod
    def Documents(
        tool_registry: IToolRegistry,
        model_registry: IModelRegistry,
        documents: DocumentService,
        secret_resolver: ISecretResolverPort | None = None,
    ) -> AgentComposerService:
        """Records in the Document Service: shared by every engine process, and
        reached through the document facade over NATS. ``documents`` is the
        engine's root service, or a view bound to a namespace of your own."""
        return AgentComposerService(
            tool_registry=tool_registry,
            model_registry=model_registry,
            spec_repository=DocumentAgentSpecRepositoryAdapter.for_engine(documents),
            secret_resolver=secret_resolver,
        )

    @staticmethod
    def FromEngine(
        engine: IEngine,
        spec_repository: IAgentSpecRepository | None = None,
        records_directory: str | Path | None = None,
        **options: Any,
    ) -> AgentComposerService:
        """Composer over a loaded engine's registries and secret service.

        Records come from ``spec_repository``, else from ``records_directory``,
        else from the engine's Document Service when it is loaded (and, for a
        module's proxy, declared). Works the same in every engine role: with
        NATS the registries are this process's own and the Document Service is
        the serving engine's. Call it after ``Engine.load()``, once modules
        published their tools.
        """
        services = engine.services
        repository = spec_repository
        if repository is None and records_directory is not None:
            repository = FileSystemAgentSpecRepositoryAdapter(records_directory)
        if repository is None and services.document_available():
            repository = DocumentAgentSpecRepositoryAdapter.for_engine(
                services.document
            )
        secret_resolver = (
            SecretServiceResolverAdapter(services.secret)
            if services.secret_available()
            else None
        )
        return AgentComposerService(
            tool_registry=services.tool_registry,
            model_registry=services.model_registry,
            spec_repository=repository,
            secret_resolver=secret_resolver,
            **options,
        )
