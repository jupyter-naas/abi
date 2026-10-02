from __future__ import annotations

from collections.abc import Iterable, Mapping
from pathlib import Path
from typing import TYPE_CHECKING, Any

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
    def FromEngine(
        engine: IEngine,
        spec_repository: IAgentSpecRepository | None = None,
        records_directory: str | Path | None = None,
        **options: Any,
    ) -> AgentComposerService:
        """Composer over a loaded engine's registries and secret service.

        Records come from ``spec_repository``, or from ``records_directory``
        when given. Call it after ``Engine.load()``, once modules published
        their tools.
        """
        services = engine.services
        repository = spec_repository
        if repository is None and records_directory is not None:
            repository = FileSystemAgentSpecRepositoryAdapter(records_directory)
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
