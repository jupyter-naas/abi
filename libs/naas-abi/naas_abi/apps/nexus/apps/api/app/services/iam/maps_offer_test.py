"""What each workspace may use of the Maps items it does not own moves into its offer
(``maps_offer_v1``): every deployment item, closed where a ``maps_grants`` row narrowed it
away, and the items other workspaces share with it, by their names there. IAM then gives
them to the workspace's people within their level, and its Denies close what it does not
use.

A real IAM (``NexusIam``) with the workspaces made as Nexus makes them, memberships through
``MEMBERSHIPS``, and a SQLite database for the rows and the recorded move. Nothing is
mocked."""

from __future__ import annotations

import json

import pytest
import pytest_asyncio
from naas_abi.apps.nexus.apps.api.app import models  # noqa: F401 - its tables in nexus_db
from naas_abi.apps.nexus.apps.api.app.models import (
    MapsGrantModel,
    OrganizationModel,
    UserModel,
    WorkspaceModel,
)
from naas_abi.apps.nexus.apps.api.app.services.iam import given_maps, maps_offer
from naas_abi.apps.nexus.apps.api.app.services.iam.container_defaults import (
    CONTAINER_DEFAULTS,
    SqlDefaultsStore,
)
from naas_abi.apps.nexus.apps.api.app.services.iam.maps_offer import Move, assignment_for
from naas_abi.apps.nexus.apps.api.app.services.iam.memberships import MEMBERSHIPS
from naas_abi.apps.nexus.apps.api.app.services.iam.names import nexus_resource
from naas_abi.apps.nexus.apps.api.app.services.iam.testing import NexusIam
from naas_abi.apps.nexus.apps.api.app.services.iam.workspace_offer import Offer, offer_of
from naas_abi.apps.nexus.apps.api.app.services.maps.permissions.permissions__schema import (
    DEPLOYMENT,
    KIND_BASEMAP,
    KIND_LAYOUT,
    MapsAssignment,
    MapsGrant,
)
from naas_abi_core.engine.call_context import as_service_account, use_call_context
from sqlalchemy import text

OFFER = Offer.of(features=["maps"])
EVERY = frozenset({KIND_LAYOUT, KIND_BASEMAP})


@pytest.fixture
def team():
    nexus = NexusIam(features_with_roles=False)
    with nexus.installed():
        nexus.grouped_org("org-1", "Acme")
        nexus.containers = {  # type: ignore[attr-defined]
            ws: nexus.grouped_workspace("org-1", ws, ws.title(), offer=OFFER).container
            for ws in ("ws-1", "ws-2", "ws-3")
        }
        for person in ("viewer2", "member2", "admin2", "stranger"):
            nexus.user(person)
        yield nexus
    CONTAINER_DEFAULTS.forget_grouped()


@pytest_asyncio.fixture
async def world(team):
    for level in ("viewer", "member", "admin"):
        await MEMBERSHIPS.grant(f"{level}2", level, team.containers["ws-2"])
    return team


def _record(nexus: NexusIam, workspace: str):
    return CONTAINER_DEFAULTS._known[nexus.containers[workspace]]


def _move(nexus: NexusIam, workspace: str, grants: list[MapsGrant]) -> Move:
    record = _record(nexus, workspace)
    return Move(
        workspace, record.container, record.access_policy_id, assignment_for(workspace, grants)
    )


def _offer(nexus: NexusIam, workspace: str) -> Offer:
    with as_service_account("api"):
        return offer_of(nexus.iam.get_policy(_record(nexus, workspace).access_policy_id).document)


def _allowed(nexus: NexusIam, user: str, action: str, resource: str) -> bool:
    with use_call_context(NexusIam.context(user)):
        return nexus.iam.authorize(action, resource).allowed


GRANTS = [
    # A deployment feed narrowed to ws-1: closed in ws-2 and ws-3.
    MapsGrant(KIND_LAYOUT, "narrowed", DEPLOYMENT, frozenset({"ws-1"})),
    # A deployment basemap available nowhere.
    MapsGrant(KIND_BASEMAP, "retired", DEPLOYMENT, frozenset()),
    # ws-1's feed shared with ws-2; ws-3's basemap shared with every workspace.
    MapsGrant(KIND_LAYOUT, "mine", "ws-1", frozenset({"ws-2"})),
    MapsGrant(KIND_BASEMAP, "sat", "ws-3", None),
]


def test_what_the_rows_let_a_workspace_use_is_its_assignment():
    assert assignment_for("ws-2", GRANTS) == MapsAssignment(
        every=EVERY,
        closed=frozenset({(KIND_LAYOUT, "narrowed"), (KIND_BASEMAP, "retired")}),
        shared=frozenset({(KIND_LAYOUT, "ws-1", "mine"), (KIND_BASEMAP, "ws-3", "sat")}),
    )
    # Its own item is its own, not shared with it; a deployment item it is listed for is open.
    assert assignment_for("ws-1", GRANTS) == MapsAssignment(
        every=EVERY,
        closed=frozenset({(KIND_BASEMAP, "retired")}),
        shared=frozenset({(KIND_BASEMAP, "ws-3", "sat")}),
    )
    # No row: every deployment item, nothing shared (what a new workspace is given).
    assert assignment_for("ws-9", []) == MapsAssignment(every=EVERY)


@pytest.mark.asyncio
async def test_each_workspace_gets_its_maps_sections_within_its_peoples_level(world):
    moves = [_move(world, ws, GRANTS) for ws in ("ws-1", "ws-2", "ws-3")]
    report = maps_offer.apply(world.iam, moves)
    assert report.to_dict()["written"] == ["ws-1", "ws-2", "ws-3"]
    assert report.closed["ws-2"] == ["basemap:retired", "layout:narrowed"]
    assert not report.failed and not report.waiting

    offer = _offer(world, "ws-2")
    assert offer.features == {"maps"}  # the rest of the offer is kept
    assert offer.maps == {
        "abi:nexus:layout/*",
        "abi:nexus:basemap/*",
        given_maps.shared_name(world.containers["ws-1"], KIND_LAYOUT, "mine"),
        given_maps.shared_name(world.containers["ws-3"], KIND_BASEMAP, "sat"),
    }
    assert offer.maps_closed == {
        "${scope}/nexus:layout/narrowed",
        "${scope}/nexus:basemap/retired",
    }
    assert given_maps.assignment_of(offer) == moves[1].assignment

    # IAM gives them to ws-2's people, each level reading them; nobody else.
    mine = nexus_resource("layout", container=world.containers["ws-1"], id="mine")
    for user in ("viewer2", "member2", "admin2"):
        assert _allowed(world, user, "nexus:GetLayout", mine), user
        assert _allowed(world, user, "nexus:GetBasemap", "abi:nexus:basemap/osm"), user
    assert not _allowed(world, "stranger", "nexus:GetLayout", mine)
    # Read, never administered: the given item stays its workspace's.
    assert not _allowed(world, "admin2", "nexus:UpdateLayout", mine)
    # What ws-2 closed is closed to its people, its other copies open.
    ws2 = world.containers["ws-2"]
    for user in ("viewer2", "admin2"):
        closed = nexus_resource("layout", container=ws2, id="narrowed")
        assert not _allowed(world, user, "nexus:GetLayout", closed), user
        assert _allowed(
            world, user, "nexus:GetLayout", nexus_resource("layout", container=ws2, id="osm")
        )

    # Idempotent: nothing written again.
    again = maps_offer.apply(world.iam, moves)
    assert again.written == [] and sorted(again.kept) == ["ws-1", "ws-2", "ws-3"]


@pytest.mark.asyncio
async def test_a_workspace_with_no_access_policy_yet_waits(world):
    waiting = Move("ws-new", None, None, assignment_for("ws-new", GRANTS))
    report = maps_offer.apply(world.iam, [_move(world, "ws-2", GRANTS), waiting])
    assert report.waiting == ["ws-new"] and report.written == ["ws-2"]


@pytest.mark.asyncio
async def test_an_item_shared_by_a_workspace_that_is_gone_is_left_out_and_named(world):
    gone = [MapsGrant(KIND_LAYOUT, "old", "ws-gone", frozenset({"ws-2"}))]
    report = maps_offer.apply(world.iam, [_move(world, "ws-2", gone)])
    assert report.dropped == ["layout:ws-gone/old in ws-2"]
    assert _offer(world, "ws-2").maps == {"abi:nexus:layout/*", "abi:nexus:basemap/*"}


async def _rows(db, workspaces: list[str]) -> None:
    db.add(UserModel(id="admin", name="Admin", email="a@example.org"))
    db.add(OrganizationModel(id="org-1", name="Acme", slug="acme", owner_id="admin"))
    for workspace in workspaces:
        db.add(
            WorkspaceModel(
                id=workspace,
                name=workspace,
                slug=workspace,
                owner_id="admin",
                organization_id="org-1",
            )
        )
    for grant in GRANTS:
        db.add(
            MapsGrantModel(
                kind=grant.kind,
                item_id=grant.item_id,
                owner_workspace_id=grant.owner,
                workspace_ids=None
                if grant.workspace_ids is None
                else json.dumps(sorted(grant.workspace_ids)),
            )
        )
    await db.commit()


@pytest.mark.asyncio
async def test_the_move_reads_the_rows_runs_once_and_is_recorded(world, nexus_db):
    async with nexus_db() as db:
        await _rows(db, ["ws-1", "ws-2", "ws-3", "ws-new"])
        store = SqlDefaultsStore(db)
        for workspace in ("ws-1", "ws-2", "ws-3"):
            await store.put(_record(world, workspace))
        await db.commit()
        # ws-new has no access policy yet: it waits, the move is not recorded.
        waiting = await maps_offer.migrate(db, world.iam)
        assert waiting is not None and waiting.waiting == ["ws-new"]
        assert waiting.written == ["ws-1", "ws-2", "ws-3"]
        await db.execute(text("DELETE FROM workspaces WHERE id = 'ws-new'"))
        await db.commit()
        report = await maps_offer.migrate(db, world.iam)
        assert report is not None and not report.failed and not report.waiting
        assert report.written == [] and len(report.kept) == 3
        assert report.shared_with_all == ["basemap:ws-3/sat"]
        found = await db.execute(
            text("SELECT report FROM iam_migrations WHERE name = :n"),
            {"n": maps_offer.MIGRATION_NAME},
        )
        assert json.loads(found.scalar_one())["closed"]["ws-2"] == [
            "basemap:retired",
            "layout:narrowed",
        ]
        assert await maps_offer.migrate(db, world.iam) is None
    assert given_maps.assignment_of(_offer(world, "ws-2")) == assignment_for("ws-2", GRANTS)
