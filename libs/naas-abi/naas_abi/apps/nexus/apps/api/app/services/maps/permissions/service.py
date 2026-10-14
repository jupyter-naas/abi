"""Maps item availability across workspaces: read the policy, change it under rules.

Rules for changing a grant (the actor is already an admin of the current workspace):

- deployment items (seeds) and "every workspace" need a platform superadmin;
- a custom item is managed from its owning workspace, and the actor may only
  add or remove workspaces they administer; others already in the list stay.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from naas_abi.apps.nexus.apps.api.app.services.maps.permissions.permissions__schema import (
    DEPLOYMENT,
    KINDS,
    MapsGrant,
    MapsPermissionError,
    MapsPermissionValidationError,
    default_grant,
)
from naas_abi.apps.nexus.apps.api.app.services.maps.permissions.port import MapsGrantStorePort


@dataclass(frozen=True)
class MapsPolicy:
    """Snapshot of one kind's stored grants, read once per request."""

    kind: str
    grants: dict[tuple[str, str], MapsGrant] = field(default_factory=dict)

    def grant(self, item_id: str, owner: str) -> MapsGrant:
        return self.grants.get((item_id, owner)) or default_grant(self.kind, item_id, owner)

    def allows(self, item_id: str, owner: str, workspace_id: str) -> bool:
        return self.grant(item_id, owner).allows(workspace_id)

    def shared_into(self, workspace_id: str) -> list[MapsGrant]:
        """Custom items other workspaces share with this one."""
        return [
            grant
            for grant in self.grants.values()
            if grant.owner not in (DEPLOYMENT, workspace_id) and grant.allows(workspace_id)
        ]


@dataclass(frozen=True)
class MapsActor:
    user_id: str
    superadmin: bool
    # Workspaces the actor administers (may grant to / revoke from).
    administered: frozenset[str]


class MapsAccess:
    def __init__(self, store: MapsGrantStorePort) -> None:
        self._store = store

    async def policy(self, kind: str) -> MapsPolicy:
        grants = await self._store.list(kind)
        return MapsPolicy(kind, {(g.item_id, g.owner): g for g in grants})

    async def forget(self, kind: str, item_id: str, owner: str) -> None:
        await self._store.delete(kind, item_id, owner)

    async def update(
        self,
        kind: str,
        item_id: str,
        owner: str,
        *,
        all_workspaces: bool,
        workspace_ids: set[str],
        actor: MapsActor,
    ) -> MapsGrant:
        if kind not in KINDS:
            raise MapsPermissionValidationError([f"unknown kind {kind!r}"])
        if owner == DEPLOYMENT and not actor.superadmin:
            raise MapsPermissionError(
                "Only a platform superadmin can change where deployment items are available"
            )
        if all_workspaces and not actor.superadmin:
            raise MapsPermissionError("Only a platform superadmin can share with every workspace")

        current = (await self.policy(kind)).grant(item_id, owner)
        if all_workspaces:
            grant = MapsGrant(kind, item_id, owner, None)
        else:
            wanted = set(workspace_ids) - {owner}
            if not actor.superadmin:
                before = set(current.workspace_ids or ())
                changed = (wanted ^ before) - set(actor.administered)
                if changed:
                    raise MapsPermissionError(
                        "You can only add or remove workspaces you administer: "
                        + ", ".join(sorted(changed))
                    )
            grant = MapsGrant(kind, item_id, owner, frozenset(wanted))

        if grant == default_grant(kind, item_id, owner):
            await self._store.delete(kind, item_id, owner)
        else:
            await self._store.save(grant, user_id=actor.user_id)
        return grant
