"""Ports and types for the ModelRegistry service.

The registry holds two kinds of entries, contributed by modules at load time:

* **Models** — concrete (canonical_id, provider, provider_model_id, Model)
  records describing a model the engine can hand back to callers.
* **Provider factories** — generic ``(provider_model_id) -> BaseChatModel``
  (or ``Embeddings``) constructors used to instantiate *off-catalog* models
  (canonical ids not registered with the registry).

Lookups are permissive: ``get(canonical_id)`` returns a registered Model when
one matches; otherwise, if a default provider is configured and has a factory,
the registry builds a Model on the fly using the canonical id as the
provider-specific id.
"""

from __future__ import annotations

from typing import Callable, Optional

from langchain_core.embeddings import Embeddings
from langchain_core.language_models.chat_models import BaseChatModel

from naas_abi_core.models.Model import (
    CanonicalModelIdLike,
    ChatModel,
    EmbeddingModel,
    Model,
    ModelProviderLike,
)


ChatProviderFactory = Callable[[str], BaseChatModel]
EmbeddingProviderFactory = Callable[[str], Embeddings]


class ModelNotFoundError(Exception):
    """Raised when a canonical id has no registered entry and no off-catalog
    construction is possible (no default provider factory available)."""


class ProviderNotConfiguredError(Exception):
    """Raised when a caller pins a lookup to a provider that has not registered
    any model or provider factory."""


class DefaultModelNotResolvedError(Exception):
    """Raised at startup when a configured default model cannot be resolved
    against the registry after all modules have loaded."""


class IModelRegistry:
    """Registry of models contributed by modules.

    Modules call ``register`` (one call per model) and optionally
    ``register_chat_provider`` / ``register_embedding_provider`` (one call per
    provider) to enable off-catalog lookups.
    """

    # ------------------------------------------------------------------ register

    def register(
        self,
        canonical_id: CanonicalModelIdLike,
        model: Model,
    ) -> None:
        """Register a model under a canonical id. The model carries its
        provider name and provider-specific id; both are read from ``model``.

        Raises ``ValueError`` if a model with the same (canonical_id, provider)
        pair is already registered.
        """
        raise NotImplementedError

    def register_chat_provider(
        self,
        provider: ModelProviderLike,
        factory: ChatProviderFactory,
    ) -> None:
        """Register a generic chat-model constructor for a provider — used to
        build off-catalog models against that provider."""
        raise NotImplementedError

    def register_embedding_provider(
        self,
        provider: ModelProviderLike,
        factory: EmbeddingProviderFactory,
    ) -> None:
        """Register a generic embedding-model constructor for a provider."""
        raise NotImplementedError

    # ------------------------------------------------------------------ lookup

    def get(
        self,
        canonical_id: CanonicalModelIdLike,
        provider: Optional[ModelProviderLike] = None,
    ) -> Model:
        """Return a Model for ``canonical_id``.

        - With ``provider``: returns the exact registered entry for
          ``(canonical_id, provider)`` if present; otherwise, if any other
          provider has a registered entry for ``canonical_id``, returns that
          (fallback). Raises ``ModelNotFoundError`` if neither exists.
        - Without ``provider``: returns the first registered entry for
          ``canonical_id``. If none is registered, falls back to the configured
          default provider's chat factory, treating ``canonical_id`` as the
          provider-specific id. Raises ``ModelNotFoundError`` if no factory is
          available.
        """
        raise NotImplementedError

    def get_chat_model(
        self,
        canonical_id: CanonicalModelIdLike,
        provider: Optional[ModelProviderLike] = None,
    ) -> ChatModel:
        """Like ``get`` but constrained to ``ChatModel``. Off-catalog lookups
        use the default provider's chat factory."""
        raise NotImplementedError

    def get_embedding_model(
        self,
        canonical_id: CanonicalModelIdLike,
        provider: Optional[ModelProviderLike] = None,
    ) -> EmbeddingModel:
        """Like ``get`` but constrained to ``EmbeddingModel``. Off-catalog
        lookups use the default provider's embedding factory."""
        raise NotImplementedError

    # ------------------------------------------------------------------ defaults

    def get_default_chat_model(self) -> ChatModel:
        """Return the chat model configured as the engine default.

        Raises ``DefaultModelNotResolvedError`` if no default is configured or
        the configured canonical id cannot be resolved."""
        raise NotImplementedError

    def get_default_embedding_model(self) -> EmbeddingModel:
        """Return the embedding model configured as the engine default.

        Raises ``DefaultModelNotResolvedError`` if no default is configured or
        the configured canonical id cannot be resolved."""
        raise NotImplementedError

    def validate_defaults(self) -> None:
        """Validate that configured defaults are resolvable after all modules
        have loaded. Called by the engine at startup. Hard-fails with
        ``DefaultModelNotResolvedError`` if any configured default is unresolved."""
        raise NotImplementedError

    # ------------------------------------------------------------------ introspection

    def list_models(self) -> list[Model]:
        """Return all registered models (any provider, any canonical id)."""
        raise NotImplementedError

    def list_canonical_ids(self) -> list[str]:
        """Return all canonical ids with at least one registered model."""
        raise NotImplementedError
