"""Tool embedder backed by the engine's model registry.

The embedding model is looked up on every call rather than captured once, so
the registry stays the single source of truth: when the configured model
changes, ``model_key`` changes with it and the tool index is rebuilt. The
registry looks it up once per sync or search through ``resolve``: with a remote
registry each lookup is a round trip.

Documents go to the model in batches of ``EMBED_BATCH_SIZE``, the most one
embed call of the engine's NATS model service accepts.
"""

from __future__ import annotations

from collections.abc import Sequence

from naas_abi_core.models.Model import EmbeddingModel
from naas_abi_core.services.model_registry.ModelRegistryPort import IModelRegistry
from naas_abi_core.services.tool_registry.ToolRegistryPort import (
    IToolEmbedderPort,
    ResolvedEmbedder,
    ToolSearchUnavailableError,
)

EMBED_BATCH_SIZE = 1024


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
        return self._key(self._model())

    @staticmethod
    def _key(model: EmbeddingModel) -> str:
        return f"{model.provider}/{model.model_id}"

    @staticmethod
    def _embed_documents(
        model: EmbeddingModel, texts: Sequence[str]
    ) -> list[list[float]]:
        vectors: list[list[float]] = []
        for start in range(0, len(texts), EMBED_BATCH_SIZE):
            batch = list(texts[start : start + EMBED_BATCH_SIZE])
            vectors.extend(model.model.embed_documents(batch))
        return vectors

    def embed_documents(self, texts: Sequence[str]) -> list[list[float]]:
        return self._embed_documents(self._model(), texts)

    def embed_query(self, text: str) -> list[float]:
        return self._model().model.embed_query(text)

    def resolve(self) -> ResolvedEmbedder:
        model = self._model()
        return ResolvedEmbedder(
            model_key=self._key(model),
            embed_documents=lambda texts: self._embed_documents(model, texts),
            embed_query=model.model.embed_query,
        )
