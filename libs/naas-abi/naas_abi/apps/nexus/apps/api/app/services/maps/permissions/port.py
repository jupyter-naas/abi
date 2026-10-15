"""Secondary ports: stored grants, and the workspaces a user may grant to."""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass

from naas_abi.apps.nexus.apps.api.app.services.maps.permissions.permissions__schema import (
    MapsGrant,
)


class MapsGrantStorePort(ABC):
    @abstractmethod
    async def list(self, kind: str) -> list[MapsGrant]:
        """Every stored grant of a kind (small: one row per shared item)."""

    @abstractmethod
    async def save(self, grant: MapsGrant, *, user_id: str | None) -> None:
        """Insert or replace the grant for (kind, item_id, owner)."""

    @abstractmethod
    async def delete(self, kind: str, item_id: str, owner: str) -> None:
        """Forget a grant (back to the default policy)."""


@dataclass(frozen=True)
class WorkspaceRef:
    id: str
    name: str


class WorkspaceDirectoryPort(ABC):
    @abstractmethod
    async def administered(self, user_id: str, *, superadmin: bool) -> list[WorkspaceRef]:
        """Workspaces the user may grant Maps items to (all of them for a superadmin)."""
