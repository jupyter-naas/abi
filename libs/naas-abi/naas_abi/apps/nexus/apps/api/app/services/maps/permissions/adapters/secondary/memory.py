from __future__ import annotations

from naas_abi.apps.nexus.apps.api.app.services.maps.permissions.permissions__schema import (
    MapsGrant,
)
from naas_abi.apps.nexus.apps.api.app.services.maps.permissions.port import (
    MapsGrantStorePort,
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
