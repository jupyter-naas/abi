from __future__ import annotations

from naas_abi_core.services.model_registry.ModelRegistryPort import IModelRegistry
from naas_abi_core.services.tool_registry.adapters.secondary.InMemoryToolIndexAdapter import (
    InMemoryToolIndexAdapter,
)
from naas_abi_core.services.tool_registry.adapters.secondary.ModelRegistryEmbedderAdapter import (
    ModelRegistryEmbedderAdapter,
)
from naas_abi_core.services.tool_registry.adapters.secondary.VectorStoreToolIndexAdapter import (
    VectorStoreToolIndexAdapter,
)
from naas_abi_core.services.tool_registry.ToolRegistryPort import IToolAccessPolicy
from naas_abi_core.services.tool_registry.ToolRegistryService import (
    ToolRegistryService,
)
from naas_abi_core.services.vector_store.VectorStoreService import VectorStoreService


class ToolRegistryFactory:
    @staticmethod
    def InMemory(
        model_registry: IModelRegistry | None = None,
        embedding_model: str | None = None,
        access_policy: IToolAccessPolicy | None = None,
    ) -> ToolRegistryService:
        """Registry with an in-process index. Search needs ``model_registry``."""
        if model_registry is None:
            return ToolRegistryService(access_policy=access_policy)
        return ToolRegistryService(
            embedder=ModelRegistryEmbedderAdapter(model_registry, embedding_model),
            index=InMemoryToolIndexAdapter(),
            access_policy=access_policy,
        )

    @staticmethod
    def VectorStore(
        vector_store: VectorStoreService,
        model_registry: IModelRegistry,
        embedding_model: str | None = None,
        collection_prefix: str = "abi_tool_registry",
        access_policy: IToolAccessPolicy | None = None,
    ) -> ToolRegistryService:
        """Registry indexing into the engine's vector store (incremental across restarts)."""
        return ToolRegistryService(
            embedder=ModelRegistryEmbedderAdapter(model_registry, embedding_model),
            index=VectorStoreToolIndexAdapter(vector_store, collection_prefix),
            access_policy=access_policy,
        )
