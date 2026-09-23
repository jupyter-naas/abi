from __future__ import annotations

from typing import TYPE_CHECKING, Literal

from naas_abi_core.services.tool_registry.ToolRegistryService import (
    ToolRegistryService,
)
from pydantic import BaseModel, ConfigDict, Field

if TYPE_CHECKING:
    from naas_abi_core.engine.IEngine import IEngine


class ToolRegistryServiceConfiguration(BaseModel):
    """Configuration for the tool registry.

    Example::

      tool_registry:
        index: auto                 # auto | memory | vector_store
        embedding_model: null       # canonical id; null = the registry's default
        collection_prefix: abi_tool_registry
        search_enabled: true

    ``auto`` indexes in the engine's vector store when one is loaded, and in
    process memory otherwise. Search stays unavailable (with an explicit error)
    until an embedding model resolves.
    """

    model_config = ConfigDict(extra="forbid")

    index: Literal["auto", "memory", "vector_store"] = "auto"
    embedding_model: str | None = None
    embedding_provider: str | None = None
    collection_prefix: str = Field(
        default="abi_tool_registry", pattern=r"^[A-Za-z0-9_-]+$"
    )
    search_enabled: bool = True

    def load(self) -> ToolRegistryService:
        return ToolRegistryService()

    def wire(self, service: ToolRegistryService, services: IEngine.Services) -> None:
        """Attach the search backend once every engine service is loaded."""
        from naas_abi_core.services.tool_registry.adapters.secondary.InMemoryToolIndexAdapter import (
            InMemoryToolIndexAdapter,
        )
        from naas_abi_core.services.tool_registry.adapters.secondary.ModelRegistryEmbedderAdapter import (
            ModelRegistryEmbedderAdapter,
        )
        from naas_abi_core.services.tool_registry.adapters.secondary.VectorStoreToolIndexAdapter import (
            VectorStoreToolIndexAdapter,
        )
        from naas_abi_core.services.tool_registry.ToolRegistryPort import (
            IToolIndexPort,
        )

        if not self.search_enabled or not services.model_registry_available():
            service.configure_search(None, None)
            return

        has_vector_store = services.vector_store_available()
        if self.index == "vector_store" and not has_vector_store:
            raise ValueError(
                "services.tool_registry.index is 'vector_store' but no vector_store "
                "service is loaded. Declare VectorStoreService in a module's "
                "dependencies, or use index 'auto' or 'memory'."
            )
        index: IToolIndexPort
        if self.index == "vector_store" or (self.index == "auto" and has_vector_store):
            index = VectorStoreToolIndexAdapter(
                services.vector_store, collection_prefix=self.collection_prefix
            )
        else:
            index = InMemoryToolIndexAdapter()

        embedder = ModelRegistryEmbedderAdapter(
            services.model_registry,
            canonical_id=self.embedding_model,
            provider=self.embedding_provider,
        )
        service.configure_search(embedder, index)
