from __future__ import annotations

from dataclasses import replace
from typing import Any

from naas_abi.apps.nexus.apps.api.app.services.maps.permissions.permissions__schema import (
    DEPLOYMENT,
    MapsAssignment,
    MapsGrant,
)
from naas_abi.apps.nexus.apps.api.app.services.maps.permissions.port import (
    MapsGrantStorePort,
    MapsOfferPort,
    WorkspaceDirectoryPort,
    WorkspaceRef,
)


class InMemoryMapsGrantStore(MapsGrantStorePort):
    """For tests and local runs without Postgres."""

    def __init__(self) -> None:
        self._grants: dict[tuple[str, str, str], MapsGrant] = {}

    async def list(self, kind: str) -> list[MapsGrant]:
        return [grant for key, grant in self._grants.items() if key[0] == kind]

    async def save(self, grant: MapsGrant, *, user_id: str | None) -> None:
        self._grants[(grant.kind, grant.item_id, grant.owner)] = grant

    async def delete(self, kind: str, item_id: str, owner: str) -> None:
        self._grants.pop((kind, item_id, owner), None)


class InMemoryMapsOffers(MapsOfferPort):
    """Each workspace's Maps assignment, for tests: a workspace not named has no
    allow-list yet. Changes are not checked (IAM's are, ``IamMapsOffers``)."""

    def __init__(self, assignments: dict[str, MapsAssignment | None] | None = None) -> None:
        self.assignments: dict[str, MapsAssignment | None] = dict(assignments or {})

    async def assignment(self, workspace_id: str) -> MapsAssignment | None:
        return self.assignments.get(workspace_id)

    async def change(
        self, user: Any, workspace_id: str, kind: str, item_id: str, owner: str, *, given: bool
    ) -> None:
        current = self.assignments.get(workspace_id) or MapsAssignment()
        if owner == DEPLOYMENT:
            every = kind in current.every
            platform, closed = set(current.platform), set(current.closed)
            if given:
                closed.discard((kind, item_id))
                if not every:
                    platform.add((kind, item_id))
            else:
                platform.discard((kind, item_id))
                if every:
                    closed.add((kind, item_id))
            updated = replace(current, platform=frozenset(platform), closed=frozenset(closed))
        else:
            shared = set(current.shared)
            (shared.add if given else shared.discard)((kind, owner, item_id))
            updated = replace(current, shared=frozenset(shared))
        self.assignments[workspace_id] = updated


class InMemoryWorkspaceDirectory(WorkspaceDirectoryPort):
    def __init__(self, workspaces: dict[str, str], admins: dict[str, set[str]]) -> None:
        self._workspaces = workspaces
        self._admins = admins  # user id -> administered workspace ids

    async def administered(self, user_id: str, *, superadmin: bool) -> list[WorkspaceRef]:
        ids = set(self._workspaces) if superadmin else self._admins.get(user_id, set())
        return sorted(
            (WorkspaceRef(i, self._workspaces[i]) for i in ids if i in self._workspaces),
            key=lambda ref: ref.name.lower(),
        )

    async def every(self) -> list[WorkspaceRef]:
        return sorted(
            (WorkspaceRef(i, name) for i, name in self._workspaces.items()),
            key=lambda ref: ref.name.lower(),
        )
