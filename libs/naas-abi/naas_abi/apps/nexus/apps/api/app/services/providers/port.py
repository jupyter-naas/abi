from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass, field


class ProviderAvailabilityPort(ABC):
    @abstractmethod
    async def list_workspace_ids_for_user(self, user_id: str) -> list[str]:
        raise NotImplementedError

    @abstractmethod
    async def list_secret_keys_for_workspaces(self, workspace_ids: list[str]) -> set[str]:
        raise NotImplementedError

    @abstractmethod
    async def list_environment_keys(self, key_names: list[str]) -> set[str]:
        raise NotImplementedError


# ---------------------------------------------------------------------------
# Model catalog store — persists editable model display properties
# ---------------------------------------------------------------------------

# Display properties that are both synced from the Python source and editable
# from the frontend. Structural identifiers (canonical_id, model_id, provider,
# module_path) are never overridable — they define which model a row is.
SYNCABLE_MODEL_FIELDS: tuple[str, ...] = (
    "name",
    "description",
    "image",
    "context_window",
)


@dataclass
class StoredModel:
    """A model row persisted in the catalog store.

    The bare ``name``/``description``/``image``/``context_window`` are the
    effective (served) values. The ``source_*`` mirror the last value seen in
    the Python source, used to detect a code-side change. ``overridden_fields``
    lists the properties a user edited in the frontend; those keep their value
    when the source changes (a warning is logged instead).
    """

    canonical_id: str
    model_id: str
    provider: str
    provider_id: str
    module_path: str
    name: str | None = None
    description: str | None = None
    image: str | None = None
    context_window: int | None = None
    source_name: str | None = None
    source_description: str | None = None
    source_image: str | None = None
    source_context_window: int | None = None
    overridden_fields: list[str] = field(default_factory=list)


class ModelCatalogStorePort(ABC):
    """Secondary port for persisting marketplace AI model display properties."""

    @abstractmethod
    async def list_all(self) -> list[StoredModel]:
        """Return every stored model row."""
        raise NotImplementedError

    @abstractmethod
    async def get(self, canonical_id: str) -> StoredModel | None:
        """Return a single stored model by canonical id, or None."""
        raise NotImplementedError

    @abstractmethod
    async def upsert(self, record: StoredModel) -> StoredModel:
        """Insert or replace a model row with the given column values."""
        raise NotImplementedError
