"""Tool embedder backed by the engine's model registry.

The embedding model is looked up on every call rather than captured once, so
the registry stays the single source of truth: when the configured model
changes, ``model_key`` changes with it and the tool index is rebuilt.
"""

from __future__ import annotations

from collections.abc import Sequence

from naas_abi_core.models.Model import EmbeddingModel
from naas_abi_core.services.model_registry.ModelRegistryPort import IModelRegistry
from naas_abi_core.services.tool_registry.ToolRegistryPort import (
    IToolEmbedderPort,
    ToolSearchUnavailableError,
)


class ModelRegistryEmbedderAdapter(IToolEmbedderPort):
    def __init__(
        self,
        registry: IModelRegistry,
        canonical_id: str | None = None,
        provider: str | None = None,
    ) -> None:
        self._registry = registry
        self._canonical_id = canonical_id
        self._provider = provider

    def _model(self) -> EmbeddingModel:
        try:
            if self._canonical_id is None:
                return self._registry.get_default_embedding_model()
            return self._registry.get_embedding_model(
                self._canonical_id, provider=self._provider
            )
        except Exception as exc:
            target = self._canonical_id or "the default"
            raise ToolSearchUnavailableError(
                f"Tool search cannot resolve {target} embedding model: {exc}"
            ) from exc

    @property
    def model_key(self) -> str:
        model = self._model()
        return f"{model.provider}/{model.model_id}"

    def embed_documents(self, texts: Sequence[str]) -> list[list[float]]:
        return self._model().model.embed_documents(list(texts))

    def embed_query(self, text: str) -> list[float]:
        return self._model().model.embed_query(text)
