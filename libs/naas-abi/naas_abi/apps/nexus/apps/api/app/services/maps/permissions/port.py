"""Secondary ports: stored grants, each workspace's offer, and the workspaces a user may
grant to."""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import Any

from naas_abi.apps.nexus.apps.api.app.services.maps.permissions.permissions__schema import (
    MapsAssignment,
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


class MapsOfferPort(ABC):
    """The Maps part of each workspace's offer (``iam/given_maps``): what a workspace may
    use of the items it does not own, read and changed there."""

    @abstractmethod
    async def assignment(self, workspace_id: str) -> MapsAssignment | None:
        """What the workspace's offer gives it; None when its access policy is no
        allow-list yet (``maps_grants`` still decides for it)."""

    @abstractmethod
    async def change(
        self, user: Any, workspace_id: str, kind: str, item_id: str, owner: str, *, given: bool
    ) -> None:
        """Give (or take) one item in the workspace's offer, written as ``user``: IAM's
        rules apply (grant only what you hold; ``PermissionDeniedError`` otherwise)."""


@dataclass(frozen=True)
class WorkspaceRef:
    id: str
    name: str


class WorkspaceDirectoryPort(ABC):
    @abstractmethod
    async def administered(self, user_id: str, *, superadmin: bool) -> list[WorkspaceRef]:
        """Workspaces the user may grant Maps items to (all of them for a superadmin)."""

    @abstractmethod
    async def every(self) -> list[WorkspaceRef]:
        """Every workspace: where an item is used is read across all of them."""
