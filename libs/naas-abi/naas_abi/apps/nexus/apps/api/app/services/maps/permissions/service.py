"""Maps item availability across workspaces: read the policy, change it under rules.

Rules for changing a grant (the actor is already an admin of the current workspace):

- deployment items (seeds) and "every workspace" need a platform superadmin;
- a custom item is managed from its owning workspace, and the actor may only
  add or remove workspaces they administer; others already in the list stay.

With ``offers`` (``MapsOfferPort``), what a workspace may use is its offer's (``iam/given_maps``,
ADR ``20261125_offer_gives_outside_resources``): ``in_workspace(kind, workspace_id)`` reads it,
and ``give`` writes it into each workspace whose answer changes, as the caller, so IAM's
held check applies under the rules above. A workspace whose access policy is no allow-list
yet still goes by ``maps_grants``: it is read for it, and a change it would need is refused
(``MapsOfferPendingError``) until the access migration has converted it.
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import dataclass, field
from typing import Any

from naas_abi.apps.nexus.apps.api.app.services.maps.permissions.permissions__schema import (
    DEPLOYMENT,
    KINDS,
    MapsAssignment,
    MapsGrant,
    MapsPermissionError,
    MapsPermissionValidationError,
    default_grant,
)
from naas_abi.apps.nexus.apps.api.app.services.maps.permissions.port import (
    MapsGrantStorePort,
    MapsOfferPort,
)


class MapsOfferPendingError(RuntimeError):
    """A workspace whose access policy is no allow-list yet: its maps are given there once
    the access migration has converted it."""


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
class OfferedMaps:
    """One workspace's Maps items, as its offer gives them (``MapsAssignment``): what
    ``MapsPolicy`` answers for that workspace."""

    kind: str
    workspace_id: str
    assignment: MapsAssignment

    def allows(self, item_id: str, owner: str, workspace_id: str) -> bool:
        if workspace_id != self.workspace_id:
            raise ValueError(f"The maps of {self.workspace_id} say nothing of {workspace_id}")
        if owner == workspace_id:
            return True
        if owner == DEPLOYMENT:
            return self.assignment.gives_platform(self.kind, item_id)
        return (owner, item_id) in self.assignment.shared_of(self.kind)

    def shared_into(self, workspace_id: str) -> list[MapsGrant]:
        """Custom items other workspaces share with this one."""
        if workspace_id != self.workspace_id:
            raise ValueError(f"The maps of {self.workspace_id} say nothing of {workspace_id}")
        return [
            MapsGrant(self.kind, item, owner, frozenset({workspace_id}))
            for owner, item in sorted(self.assignment.shared_of(self.kind))
            if owner != workspace_id
        ]


@dataclass(frozen=True)
class MapsActor:
    user_id: str
    superadmin: bool
    # Workspaces the actor administers (may grant to / revoke from).
    administered: frozenset[str]


class MapsAccess:
    def __init__(self, store: MapsGrantStorePort, offers: MapsOfferPort | None = None) -> None:
        self._store = store
        self._offers = offers

    @property
    def offers(self) -> MapsOfferPort | None:
        return self._offers

    async def policy(self, kind: str) -> MapsPolicy:
        """The stored grants of ``kind`` (``maps_grants``)."""
        grants = await self._store.list(kind)
        return MapsPolicy(kind, {(g.item_id, g.owner): g for g in grants})

    async def in_workspace(self, kind: str, workspace_id: str) -> MapsPolicy | OfferedMaps:
        """What ``workspace_id`` may use of ``kind``: its offer's when its access policy is
        an allow-list (``OfferedMaps``); else the stored grants."""
        if self._offers is not None:
            assignment = await self._offers.assignment(workspace_id)
            if assignment is not None:
                return OfferedMaps(kind, workspace_id, assignment)
        return await self.policy(kind)

    async def assignments(self, workspace_ids: Sequence[str]) -> dict[str, MapsAssignment | None]:
        """Each workspace's offer (None: no allow-list yet), read once for a request."""
        if self._offers is None:
            return dict.fromkeys(workspace_ids)
        return {w: await self._offers.assignment(w) for w in workspace_ids}

    @staticmethod
    def _uses(
        kind: str,
        item_id: str,
        owner: str,
        workspace_id: str,
        assignment: MapsAssignment | None,
        stored: MapsPolicy,
    ) -> bool:
        if assignment is None:
            return stored.allows(item_id, owner, workspace_id)
        return OfferedMaps(kind, workspace_id, assignment).allows(item_id, owner, workspace_id)

    async def view(
        self,
        kind: str,
        item_id: str,
        owner: str,
        *,
        workspaces: Sequence[str],
        assignments: Mapping[str, MapsAssignment | None] | None = None,
        stored: MapsPolicy | None = None,
    ) -> MapsGrant:
        """Where the item is used, as a grant: the stored one without ``offers``; else the
        workspaces (of ``workspaces``, every one) whose offer, or stored grant for one with
        no allow-list yet, lets them use it. "Every workspace" when each but its owner
        does (one other at least, for a workspace's own item)."""
        if stored is None:
            stored = await self.policy(kind)
        if self._offers is None:
            return stored.grant(item_id, owner)
        if assignments is None:
            assignments = await self.assignments(workspaces)
        others = [w for w in workspaces if w != owner]
        using = frozenset(
            w for w in others if self._uses(kind, item_id, owner, w, assignments.get(w), stored)
        )
        every = len(using) == len(others) and (owner == DEPLOYMENT or bool(others))
        return MapsGrant(kind, item_id, owner, None if every else using)

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

    async def give(
        self,
        kind: str,
        item_id: str,
        owner: str,
        *,
        all_workspaces: bool,
        workspace_ids: set[str],
        actor: MapsActor,
        user: Any,
        workspaces: Sequence[str],
    ) -> MapsGrant:
        """``update``'s change, written into each workspace's offer whose answer changes
        (of ``workspaces``, every one), as ``user``. The rules above first; then IAM's
        (``PermissionDeniedError`` for an item the caller does not hold, or an offer they
        may not change). A workspace with no allow-list yet that would change refuses the
        whole change before anything is written (``MapsOfferPendingError``). The writes
        are one per workspace: a refusal stops the ones after it."""
        if self._offers is None:
            raise RuntimeError("No offers to give maps in")
        if kind not in KINDS:
            raise MapsPermissionValidationError([f"unknown kind {kind!r}"])
        if owner == DEPLOYMENT and not actor.superadmin:
            raise MapsPermissionError(
                "Only a platform superadmin can change where deployment items are available"
            )
        if all_workspaces and not actor.superadmin:
            raise MapsPermissionError("Only a platform superadmin can share with every workspace")
        others = [w for w in workspaces if w != owner]
        unknown = sorted(set(workspace_ids) - set(workspaces) - {owner})
        if unknown:
            raise MapsPermissionValidationError(["unknown workspaces: " + ", ".join(unknown)])
        wanted = set(others) if all_workspaces else set(workspace_ids) - {owner}
        assignments = await self.assignments(others)
        stored = await self.policy(kind)
        before = {w for w in others if self._uses(kind, item_id, owner, w, assignments[w], stored)}
        changed = sorted(wanted ^ before)
        if not actor.superadmin:
            beyond = sorted(set(changed) - set(actor.administered))
            if beyond:
                raise MapsPermissionError(
                    "You can only add or remove workspaces you administer: " + ", ".join(beyond)
                )
        pending = [w for w in changed if assignments[w] is None]
        if pending:
            raise MapsOfferPendingError(
                "These workspaces' access policies are not allow-lists yet: their maps are "
                "given there once the access migration has converted them: " + ", ".join(pending)
            )
        for workspace_id in changed:
            await self._offers.change(
                user, workspace_id, kind, item_id, owner, given=workspace_id in wanted
            )
        return await self.view(kind, item_id, owner, workspaces=workspaces, stored=stored)
