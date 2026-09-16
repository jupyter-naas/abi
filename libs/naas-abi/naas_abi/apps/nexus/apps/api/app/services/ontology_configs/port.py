"""Ontology configs service port + HTTP schemas.

Per-workspace enable state for the reference (module TTL) ontology
catalog — the ontology counterpart of ``services/apps/port.py``.

* Persistence port (``OntologyConfigPersistencePort``) + records/inputs
  used by the secondary adapter.
* HTTP-bound pydantic schemas returned/accepted by the FastAPI primary
  adapter.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass
from datetime import datetime

from pydantic import BaseModel

# ---------------------------------------------------------------------------
# HTTP schemas (pydantic) — consumed by the FastAPI primary adapter
# ---------------------------------------------------------------------------


class OntologyCatalogItem(BaseModel):
    """A reference ontology file discovered from a loaded module."""

    # Identity
    ontology_id: str            # stable catalog key, "<module>:<filename.ttl>"
    path: str                   # absolute file path (what ?ontology= uses)

    # Display
    name: str
    module_name: str
    submodule_name: str | None = None
    description: str | None = None
    license: str | None = None
    contributors: list[str] = []
    date: str | None = None
    imports: list[str] = []

    # Per-workspace enable state. Missing config rows default to off.
    enabled: bool = False


class OntologyCatalogResponse(BaseModel):
    ontologies: list[OntologyCatalogItem]


class OntologyConfigCreate(BaseModel):
    """Body for ``POST /api/ontology-configs/{workspace_id}``."""

    ontology_id: str
    enabled: bool = True


class OntologyConfigUpdate(BaseModel):
    """Body for ``PATCH /api/ontology-configs/{workspace_id}/{ontology_id:path}``."""

    enabled: bool | None = None


# ---------------------------------------------------------------------------
# Persistence port + records (consumed by secondary adapters)
# ---------------------------------------------------------------------------


@dataclass
class OntologyConfigRecord:
    """Per-workspace config row for a single reference ontology."""

    id: str
    workspace_id: str
    ontology_id: str
    enabled: bool
    created_at: datetime
    updated_at: datetime


@dataclass
class OntologyConfigCreateInput:
    workspace_id: str
    ontology_id: str
    enabled: bool = True


@dataclass
class OntologyConfigUpdateInput:
    enabled: bool | None = None


class OntologyConfigPersistencePort(ABC):
    @abstractmethod
    async def list_by_workspace(self, workspace_id: str) -> list[OntologyConfigRecord]:
        """Return every per-workspace ontology config record."""

    @abstractmethod
    async def get(
        self, workspace_id: str, ontology_id: str
    ) -> OntologyConfigRecord | None:
        """Return the record for a single (workspace, ontology) pair, or None."""

    @abstractmethod
    async def create(self, data: OntologyConfigCreateInput) -> OntologyConfigRecord:
        """Insert a new config row.

        Implementations should let the service detect an existing
        (workspace_id, ontology_id) pair before calling this.
        """

    @abstractmethod
    async def update(
        self, workspace_id: str, ontology_id: str, updates: OntologyConfigUpdateInput
    ) -> OntologyConfigRecord | None:
        """Update an existing config row; returns ``None`` if absent."""

    @abstractmethod
    async def delete(self, workspace_id: str, ontology_id: str) -> bool:
        """Remove a config row. Returns True if a row was removed."""
