"""In-memory ModelRegistry service.

Lifecycle:

1. Engine constructs ``ModelRegistryService(default_chat_model=..., ...)``.
2. Each module, during ``on_load``, calls ``register(...)`` for every model it
   ships and (optionally) ``register_chat_provider`` /
   ``register_embedding_provider`` for the providers it owns.
3. After all modules have loaded, the engine calls ``validate_defaults()`` —
   hard-fails if the configured defaults can't be resolved.
"""

from __future__ import annotations

from typing import Optional

from naas_abi_core.models.Model import (
    CanonicalModelIdLike,
    ChatModel,
    EmbeddingModel,
    Model,
    ModelProviderLike,
    ModelType,
)
from naas_abi_core.services.model_registry.ModelRegistryPort import (
    ChatProviderFactory,
    DefaultModelNotResolvedError,
    EmbeddingProviderFactory,
    IModelRegistry,
    ModelNotFoundError,
    ProviderNotConfiguredError,
)
from naas_abi_core.services.ServiceBase import ServiceBase


def _norm(value: CanonicalModelIdLike | ModelProviderLike | None) -> Optional[str]:
    """Normalize an enum-or-string identifier to a plain string."""
    if value is None:
        return None
    return str(value)


class ModelRegistryService(ServiceBase, IModelRegistry):
    """In-memory registry. Thread-safety: registration is expected to happen
    during single-threaded module load; reads after load are safe."""

    def __init__(
        self,
        default_chat_model: Optional[str] = None,
        default_embedding_model: Optional[str] = None,
        default_provider: Optional[str] = None,
    ) -> None:
        super().__init__()
        self._default_chat_model = _norm(default_chat_model)
        self._default_embedding_model = _norm(default_embedding_model)
        self._default_provider = _norm(default_provider)

        # canonical_id -> { provider -> Model }
        self._models: dict[str, dict[str, Model]] = {}
        self._chat_providers: dict[str, ChatProviderFactory] = {}
        self._embedding_providers: dict[str, EmbeddingProviderFactory] = {}

    # ------------------------------------------------------------------ register

    def register(
        self,
        canonical_id: CanonicalModelIdLike,
        model: Model,
    ) -> None:
        cid = _norm(canonical_id)
        assert cid is not None
        provider = model.provider
        bucket = self._models.setdefault(cid, {})
        if provider in bucket:
            raise ValueError(
                f"Model already registered for canonical_id={cid!r} "
                f"provider={provider!r}"
            )
        bucket[provider] = model

    def register_chat_provider(
        self,
        provider: ModelProviderLike,
        factory: ChatProviderFactory,
    ) -> None:
        name = _norm(provider)
        assert name is not None
        self._chat_providers[name] = factory

    def register_embedding_provider(
        self,
        provider: ModelProviderLike,
        factory: EmbeddingProviderFactory,
    ) -> None:
        name = _norm(provider)
        assert name is not None
        self._embedding_providers[name] = factory

    # ------------------------------------------------------------------ lookup

    def _lookup_registered(
        self, canonical_id: str, provider: Optional[str]
    ) -> Optional[Model]:
        bucket = self._models.get(canonical_id)
        if not bucket:
            return None
        if provider is not None:
            if provider in bucket:
                return bucket[provider]
            # Provider pinned but not present — fall back to any other provider
            # that has this canonical id registered.
            return next(iter(bucket.values()))
        return next(iter(bucket.values()))

    def get(
        self,
        canonical_id: CanonicalModelIdLike,
        provider: Optional[ModelProviderLike] = None,
    ) -> Model:
        cid = _norm(canonical_id)
        assert cid is not None
        prov = _norm(provider)

        if prov is not None and prov not in self._chat_providers and prov not in self._embedding_providers and prov not in {m.provider for bucket in self._models.values() for m in bucket.values()}:
            raise ProviderNotConfiguredError(
                f"Provider {prov!r} has no registered models or factories"
            )

        hit = self._lookup_registered(cid, prov)
        if hit is not None:
            return hit

        # Off-catalog: route through default provider's chat factory.
        # (``get`` without a model type defaults to chat.)
        return self._build_off_catalog_chat(cid, prov)

    def get_chat_model(
        self,
        canonical_id: CanonicalModelIdLike,
        provider: Optional[ModelProviderLike] = None,
    ) -> ChatModel:
        cid = _norm(canonical_id)
        assert cid is not None
        prov = _norm(provider)

        hit = self._lookup_registered(cid, prov)
        if hit is not None:
            if not isinstance(hit, ChatModel):
                raise ModelNotFoundError(
                    f"Registered model for canonical_id={cid!r} provider={hit.provider!r} "
                    f"is not a ChatModel (got {type(hit).__name__})"
                )
            return hit

        return self._build_off_catalog_chat(cid, prov)

    def get_embedding_model(
        self,
        canonical_id: CanonicalModelIdLike,
        provider: Optional[ModelProviderLike] = None,
    ) -> EmbeddingModel:
        cid = _norm(canonical_id)
        assert cid is not None
        prov = _norm(provider)

        hit = self._lookup_registered(cid, prov)
        if hit is not None:
            if not isinstance(hit, EmbeddingModel):
                raise ModelNotFoundError(
                    f"Registered model for canonical_id={cid!r} provider={hit.provider!r} "
                    f"is not an EmbeddingModel (got {type(hit).__name__})"
                )
            return hit

        return self._build_off_catalog_embedding(cid, prov)

    # ------------------------------------------------------------------ off-catalog

    def _resolve_off_catalog_provider(self, requested: Optional[str]) -> str:
        # Caller-pinned provider wins over the configured default.
        target = requested or self._default_provider
        if target is None:
            raise ModelNotFoundError(
                "Model is not registered and no default_provider is configured "
                "for off-catalog routing"
            )
        return target

    def _build_off_catalog_chat(
        self, canonical_id: str, requested_provider: Optional[str]
    ) -> ChatModel:
        provider = self._resolve_off_catalog_provider(requested_provider)
        factory = self._chat_providers.get(provider)
        if factory is None:
            raise ModelNotFoundError(
                f"Cannot construct off-catalog chat model {canonical_id!r}: "
                f"provider {provider!r} has no registered chat factory"
            )
        base = factory(canonical_id)
        return ChatModel(model_id=canonical_id, provider=provider, model=base)

    def _build_off_catalog_embedding(
        self, canonical_id: str, requested_provider: Optional[str]
    ) -> EmbeddingModel:
        provider = self._resolve_off_catalog_provider(requested_provider)
        factory = self._embedding_providers.get(provider)
        if factory is None:
            raise ModelNotFoundError(
                f"Cannot construct off-catalog embedding model {canonical_id!r}: "
                f"provider {provider!r} has no registered embedding factory"
            )
        embeddings = factory(canonical_id)
        return EmbeddingModel(
            model_id=canonical_id, provider=provider, model=embeddings
        )

    # ------------------------------------------------------------------ defaults

    def get_default_chat_model(self) -> ChatModel:
        if self._default_chat_model is None:
            raise DefaultModelNotResolvedError(
                "No default chat model configured (set services.model_registry.default_chat_model)"
            )
        return self.get_chat_model(self._default_chat_model)

    def get_default_embedding_model(self) -> EmbeddingModel:
        if self._default_embedding_model is None:
            raise DefaultModelNotResolvedError(
                "No default embedding model configured (set services.model_registry.default_embedding_model)"
            )
        return self.get_embedding_model(self._default_embedding_model)

    def validate_defaults(self) -> None:
        """Resolve the configured defaults. Hard-fail on any unresolved id.

        A configured default must be registered — off-catalog construction is
        an explicit caller-side opt-in, never an implicit default."""
        errors: list[str] = []

        if self._default_chat_model is not None:
            if not self._has_registered(self._default_chat_model, ModelType.CHAT):
                errors.append(
                    f"default_chat_model={self._default_chat_model!r} is not registered "
                    f"as a chat model"
                )

        if self._default_embedding_model is not None:
            if not self._has_registered(
                self._default_embedding_model, ModelType.EMBEDDING
            ):
                errors.append(
                    f"default_embedding_model={self._default_embedding_model!r} is not "
                    f"registered as an embedding model"
                )

        if errors:
            raise DefaultModelNotResolvedError("; ".join(errors))

    def _has_registered(self, canonical_id: str, model_type: ModelType) -> bool:
        bucket = self._models.get(canonical_id)
        if not bucket:
            return False
        return any(getattr(m, "model_type", None) == model_type for m in bucket.values())

    # ------------------------------------------------------------------ introspection

    def list_models(self) -> list[Model]:
        out: list[Model] = []
        for bucket in self._models.values():
            out.extend(bucket.values())
        return out

    def list_canonical_ids(self) -> list[str]:
        return list(self._models.keys())
