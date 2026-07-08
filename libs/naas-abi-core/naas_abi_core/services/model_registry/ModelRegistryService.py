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
    ) -> None:
        super().__init__()
        self._default_chat_model = _norm(default_chat_model)
        self._default_embedding_model = _norm(default_embedding_model)

        # canonical_id -> { provider -> [Model, ...] }
        # Multiple entries per (canonical_id, provider) are allowed: the first
        # registered wins on lookup. Callers that need a specific variant can
        # import the model file directly and bypass the registry.
        self._models: dict[str, dict[str, list[Model]]] = {}
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
        bucket.setdefault(provider, []).append(model)

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
            entries = bucket.get(provider)
            if entries:
                return entries[0]
            # Provider pinned but not present — fall back to any other provider
            # that has this canonical id registered (first one wins).
            for other_entries in bucket.values():
                if other_entries:
                    return other_entries[0]
            return None
        for entries in bucket.values():
            if entries:
                return entries[0]
        return None

    def get(
        self,
        canonical_id: CanonicalModelIdLike,
        provider: Optional[ModelProviderLike] = None,
    ) -> Model:
        cid = _norm(canonical_id)
        assert cid is not None
        prov = _norm(provider)

        if (
            prov is not None
            and prov not in self._chat_providers
            and prov not in self._embedding_providers
            and prov not in {
                model.provider
                for bucket in self._models.values()
                for entries in bucket.values()
                for model in entries
            }
        ):
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

    @staticmethod
    def _require_off_catalog_provider(
        canonical_id: str, requested_provider: Optional[str]
    ) -> str:
        if requested_provider is None:
            raise ModelNotFoundError(
                f"Model {canonical_id!r} is not registered. To use it anyway, "
                f"pass provider= explicitly so the registry knows which provider "
                f"factory to route through."
            )
        return requested_provider

    def _build_off_catalog_chat(
        self, canonical_id: str, requested_provider: Optional[str]
    ) -> ChatModel:
        provider = self._require_off_catalog_provider(canonical_id, requested_provider)
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
        provider = self._require_off_catalog_provider(canonical_id, requested_provider)
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

    @property
    def default_chat_model_id(self) -> Optional[str]:
        return self._default_chat_model

    @property
    def default_embedding_model_id(self) -> Optional[str]:
        return self._default_embedding_model

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
                    self._build_unresolved_default_message(
                        config_key="default_chat_model",
                        configured_id=self._default_chat_model,
                        model_type=ModelType.CHAT,
                    )
                )

        if self._default_embedding_model is not None:
            if not self._has_registered(
                self._default_embedding_model, ModelType.EMBEDDING
            ):
                errors.append(
                    self._build_unresolved_default_message(
                        config_key="default_embedding_model",
                        configured_id=self._default_embedding_model,
                        model_type=ModelType.EMBEDDING,
                    )
                )

        if errors:
            raise DefaultModelNotResolvedError("\n\n".join(errors))

    def _build_unresolved_default_message(
        self,
        config_key: str,
        configured_id: str,
        model_type: ModelType,
    ) -> str:
        type_label = "chat" if model_type == ModelType.CHAT else "embedding"
        article = "a" if model_type == ModelType.CHAT else "an"
        registered = sorted(self._registered_ids_for_type(model_type))
        registered_line = (
            ", ".join(repr(i) for i in registered) if registered else "(none)"
        )
        return (
            f"{config_key}={configured_id!r} is not registered as {article} {type_label} model.\n"
            f"  → set in your engine config under services.model_registry.{config_key}, "
            f"but no loaded module registered {article} {type_label} model with this id.\n"
            f"  → likely cause: the module that ships {configured_id!r} is not enabled "
            f"in your `modules:` config (or is declared as a `#soft` dependency that "
            f"hasn't been explicitly enabled). Add or enable that module, or change "
            f"{config_key} to one of the registered ids below.\n"
            f"  → currently registered {type_label} model ids: {registered_line}"
        )

    def _registered_ids_for_type(self, model_type: ModelType) -> set[str]:
        return {
            canonical_id
            for canonical_id, bucket in self._models.items()
            for entries in bucket.values()
            for m in entries
            if getattr(m, "model_type", None) == model_type
        }

    def _has_registered(self, canonical_id: str, model_type: ModelType) -> bool:
        bucket = self._models.get(canonical_id)
        if not bucket:
            return False
        return any(
            getattr(m, "model_type", None) == model_type
            for entries in bucket.values()
            for m in entries
        )

    # ------------------------------------------------------------------ introspection

    def list_models(self) -> list[Model]:
        out: list[Model] = []
        for bucket in self._models.values():
            for entries in bucket.values():
                out.extend(entries)
        return out

    def list_canonical_ids(self) -> list[str]:
        return list(self._models.keys())
