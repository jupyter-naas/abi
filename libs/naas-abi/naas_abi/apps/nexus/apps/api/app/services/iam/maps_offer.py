"""What each workspace may use of the Maps items it does not own moves into its offer, once
(``maps_offer_v1``; ADR ``20261125_offer_gives_outside_resources``, decision 5 and "Maps").

An earlier version decided it per item, in ``maps_grants``: a deployment item (a seed) was
used by every workspace unless a row narrowed it to a list (or to none); a workspace's own
item was used at home unless a row shared it with a list, or with every workspace. Nexus
filtered by it. The offer says it now: the Maps part of "<W> access" (``given_maps``).

For each workspace Nexus records, its effective assignment becomes its Maps sections, as
``maps_grants`` decided it at the time of the move:

- every deployment feed and basemap is given (``abi:nexus:<kind>/*``: the ones added later
  too, as with no row); each one a row narrows away from the workspace is closed there
  (``OfferMapsDeny``, ``OfferBasemapsDeny``);
- each item another workspace shares with it (by list, or with every workspace) is given
  by its name in that workspace. One whose workspace is gone is left out, and named.

What the workspace hides (``maps_settings.hidden_*``) is its display choice, and stays
there. ``maps_grants`` is kept: a workspace whose access policy is no allow-list yet still
goes by it (``maps/permissions``). A workspace with no access policy yet waits for a start
where it has one. Recorded in ``iam_migrations`` once nothing failed or waits. As ``api``.
"""

from __future__ import annotations

import json
import logging
from collections.abc import Iterable, Mapping, Sequence
from dataclasses import dataclass, field, replace
from typing import Any

from naas_abi.apps.nexus.apps.api.app.services.iam import given_maps, offer_moves
from naas_abi.apps.nexus.apps.api.app.services.iam.names import (
    is_workspace_container,
    workspace_container,
    workspace_of,
)
from naas_abi.apps.nexus.apps.api.app.services.iam.workspace_offer import (
    offer_of,
    with_offer,
)
from naas_abi.apps.nexus.apps.api.app.services.maps.permissions.permissions__schema import (
    DEPLOYMENT,
    KINDS,
    MapsAssignment,
    MapsGrant,
)
from naas_abi_core.engine.call_context import as_service_account
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession
from starlette.concurrency import run_in_threadpool

logger = logging.getLogger(__name__)

MIGRATION_NAME = "maps_offer_v1"


def assignment_for(workspace: str, grants: Iterable[MapsGrant]) -> MapsAssignment:
    """What ``maps_grants`` (``grants``, every row) let ``workspace`` use of the items it
    does not own: every deployment item but those a row narrows away from it, and the
    items other workspaces share with it."""
    closed: set[tuple[str, str]] = set()
    shared: set[tuple[str, str, str]] = set()
    for grant in grants:
        if grant.kind not in KINDS:
            continue
        if grant.owner == DEPLOYMENT:
            if not grant.allows(workspace):
                closed.add((grant.kind, grant.item_id))
        elif grant.owner != workspace and grant.allows(workspace):
            shared.add((grant.kind, grant.owner, grant.item_id))
    return MapsAssignment(
        every=frozenset(KINDS), closed=frozenset(closed), shared=frozenset(shared)
    )


@dataclass(frozen=True)
class Move:
    """One workspace: its container, its "<W> access" and what it may use."""

    workspace: str
    container: str | None
    policy_id: str | None
    assignment: MapsAssignment


@dataclass
class Report:
    # Workspaces whose "<W> access" now says what they use.
    written: list[str] = field(default_factory=list)
    # Workspaces whose offer said it already.
    kept: list[str] = field(default_factory=list)
    # Workspaces with no access policy yet (the next start).
    waiting: list[str] = field(default_factory=list)
    # Workspaces that used a deployment item a row narrowed away from them: closed there.
    closed: dict[str, list[str]] = field(default_factory=dict)
    # Items shared with every workspace: given to each now, not to one made later.
    shared_with_all: list[str] = field(default_factory=list)
    # Items shared by a workspace that is gone: not given.
    dropped: list[str] = field(default_factory=list)
    failed: dict[str, str] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {
            "written": sorted(self.written),
            "kept": len(self.kept),
            "waiting": sorted(self.waiting),
            "closed": dict(sorted(self.closed.items())),
            "shared_with_all": sorted(self.shared_with_all),
            "dropped": sorted(self.dropped),
            "failed": dict(sorted(self.failed.items())),
        }


def apply(
    iam: Any, moves: Sequence[Move], *, containers: Mapping[str, str] | None = None
) -> Report:
    """Write each workspace's Maps assignment into its "<W> access", its other sections and
    statements kept. ``containers``: ``{workspace: container}`` of the workspaces that
    share (one missing is gone). As ``api``. Idempotent: a second pass writes nothing."""
    report = Report()
    known = dict(containers or {})
    known.update({m.workspace: m.container for m in moves if m.container})
    with as_service_account("api"):
        for move in moves:
            try:
                if move.policy_id is None or move.container is None:
                    report.waiting.append(move.workspace)
                    continue
                for kind, owner, item in sorted(move.assignment.shared):
                    if owner not in known:
                        report.dropped.append(f"{kind}:{owner}/{item} in {move.workspace}")
                policy = iam.get_policy(move.policy_id)
                held = offer_of(policy.document)
                fields = given_maps.fields_of(move.assignment, container_of=known.get)
                wanted = replace(held, **fields)
                if move.assignment.closed:
                    report.closed[move.workspace] = sorted(
                        f"{kind}:{item}" for kind, item in move.assignment.closed
                    )
                if wanted == held:
                    report.kept.append(move.workspace)
                    continue
                iam.update_policy(
                    policy.id,
                    expected_revision=policy.revision,
                    document=with_offer(policy.document, wanted),
                )
                report.written.append(move.workspace)
            except Exception as exc:  # noqa: BLE001 - reported, retried at the next start
                report.failed[move.workspace] = str(exc)
    return report


# -- what Nexus records -------------------------------------------------------------------


def _grant(kind: Any, item_id: Any, owner: Any, raw: Any) -> MapsGrant:
    ids = None if raw is None else frozenset(str(v) for v in json.loads(str(raw)))
    return MapsGrant(str(kind), str(item_id), str(owner or ""), ids)


async def grants_of(db: AsyncSession) -> list[MapsGrant]:
    """Every row of ``maps_grants``."""
    rows = (
        await db.execute(
            text("SELECT kind, item_id, owner_workspace_id, workspace_ids FROM maps_grants")
        )
    ).all()
    return [_grant(*row) for row in rows]


async def moves_of(db: AsyncSession) -> tuple[list[Move], dict[str, str], MapsGrantsInfo]:
    """Each workspace Nexus records, with its access policy and what it may use; the
    container of every workspace (``{workspace: container}``); and what the rows said
    beyond (items shared with every workspace)."""
    policies = await offer_moves.access_policies(db)
    recorded = {
        workspace: (container, policy_id)
        for container, policy_id in policies.items()
        if is_workspace_container(container) and (workspace := workspace_of(container))
    }
    rows = (await db.execute(text("SELECT id, organization_id FROM workspaces ORDER BY id"))).all()
    containers = {
        str(w): recorded.get(str(w), (None, None))[0] or workspace_container(org, str(w))
        for w, org in rows
    }
    grants = await grants_of(db)
    moves = [
        Move(
            str(w),
            recorded.get(str(w), (None, None))[0],
            recorded.get(str(w), (None, None))[1],
            assignment_for(str(w), grants),
        )
        for w, _org in rows
    ]
    return moves, containers, MapsGrantsInfo.of(grants)


@dataclass(frozen=True)
class MapsGrantsInfo:
    """What the rows said that an offer cannot keep: items shared with every workspace."""

    shared_with_all: tuple[str, ...] = ()

    @classmethod
    def of(cls, grants: Iterable[MapsGrant]) -> MapsGrantsInfo:
        return cls(
            tuple(
                sorted(
                    f"{g.kind}:{g.owner}/{g.item_id}"
                    for g in grants
                    if g.owner != DEPLOYMENT and g.workspace_ids is None
                )
            )
        )


async def migrate(db: AsyncSession, iam: Any) -> Report | None:
    """Once: what each workspace may use of the Maps items into its offer. None when
    recorded."""
    if await offer_moves.recorded(db, MIGRATION_NAME):
        return None
    moves, containers, info = await moves_of(db)
    report = await run_in_threadpool(lambda: apply(iam, moves, containers=containers))
    report.shared_with_all = list(info.shared_with_all)
    if report.written:
        from naas_abi.apps.nexus.apps.api.app.services.iam.authz import AUTHZ

        AUTHZ.forget_offers()
    if report.failed or report.waiting:
        logger.warning(
            "Maps into the offer: not recorded yet (next start): failed %s, waiting %s",
            report.failed,
            report.waiting,
        )
        return report
    await offer_moves.record(db, MIGRATION_NAME, report.to_dict())
    if report.shared_with_all:
        logger.warning(
            "Maps into the offer: shared with every workspace, given to each now and not "
            "to a workspace made later: %s",
            report.shared_with_all,
        )
    logger.info("Maps in the offer: %s", report.to_dict())
    return report


__all__ = [
    "MIGRATION_NAME",
    "MapsGrantsInfo",
    "Move",
    "Report",
    "apply",
    "assignment_for",
    "grants_of",
    "migrate",
    "moves_of",
]
