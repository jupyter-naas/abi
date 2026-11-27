"""What a workspace may use of the Maps items it does not own is its offer's (``iam/given_maps``,
ADR ``20261125_offer_gives_outside_resources``): its listing follows the offer, alike for
each level, and Settings › Maps › Access writes the offer of each workspace a change touches,
as the caller, IAM's held check applying. A workspace whose access policy is no allow-list
yet still goes by ``maps_grants``.

A real IAM (``NexusIam``) with an organization and its workspaces made as Nexus makes them,
memberships through ``MEMBERSHIPS``, the real offer service, and the real routes over
in-memory Maps stores. Nothing about who may do what is mocked."""

from __future__ import annotations

from dataclasses import replace
from types import SimpleNamespace

import pytest
import pytest_asyncio
from fastapi import FastAPI
from naas_abi.apps.nexus.apps.api.app.services.feature_access import runtime as offers_runtime
from naas_abi.apps.nexus.apps.api.app.services.feature_access.service import (
    FeatureAccessService,
)
from naas_abi.apps.nexus.apps.api.app.services.graph.testing import acting_as_header, client
from naas_abi.apps.nexus.apps.api.app.services.iam import given_maps
from naas_abi.apps.nexus.apps.api.app.services.iam.authz import AUTHZ
from naas_abi.apps.nexus.apps.api.app.services.iam.container_defaults import (
    CONTAINER_DEFAULTS,
    platform_maps,
)
from naas_abi.apps.nexus.apps.api.app.services.iam.memberships import MEMBERSHIPS
from naas_abi.apps.nexus.apps.api.app.services.iam.testing import NexusIam
from naas_abi.apps.nexus.apps.api.app.services.iam.workspace_offer import Offer, offer_of
from naas_abi.apps.nexus.apps.api.app.services.iam_admin.adapters.secondary.engine import (
    EngineIamGateway,
)
from naas_abi.apps.nexus.apps.api.app.services.iam_admin.testing import MemoryAudit
from naas_abi.apps.nexus.apps.api.app.services.maps.basemaps.adapters.secondary.memory import (
    InMemoryMapsBasemapStore,
)
from naas_abi.apps.nexus.apps.api.app.services.maps.basemaps.service import MapsBasemapService
from naas_abi.apps.nexus.apps.api.app.services.maps.feed_layers.adapters.secondary.memory import (
    InMemoryMapsFeedLayerStore,
)
from naas_abi.apps.nexus.apps.api.app.services.maps.feed_layers.service import (
    MapsFeedLayerService,
)
from naas_abi.apps.nexus.apps.api.app.services.maps.layouts.adapters.primary import (
    maps_layouts__primary_adapter__FastAPI as layouts_api,
)
from naas_abi.apps.nexus.apps.api.app.services.maps.layouts.adapters.secondary.memory import (
    InMemoryMapsLayoutStore,
)
from naas_abi.apps.nexus.apps.api.app.services.maps.layouts.layouts__schema import (
    FEED_GEOJSON_URL,
    MapsLayout,
)
from naas_abi.apps.nexus.apps.api.app.services.maps.layouts.service import MapsLayoutService
from naas_abi.apps.nexus.apps.api.app.services.maps.permissions.adapters.primary import (
    maps_permissions__primary_adapter__FastAPI as permissions_api,
)
from naas_abi.apps.nexus.apps.api.app.services.maps.permissions.adapters.secondary.memory import (
    InMemoryMapsGrantStore,
    InMemoryWorkspaceDirectory,
)
from naas_abi.apps.nexus.apps.api.app.services.maps.permissions.adapters.secondary.offer import (
    IamMapsOffers,
)
from naas_abi.apps.nexus.apps.api.app.services.maps.permissions.permissions__schema import (
    DEPLOYMENT,
    KIND_LAYOUT,
    MapsGrant,
)
from naas_abi.apps.nexus.apps.api.app.services.maps.permissions.service import MapsAccess
from naas_abi.apps.nexus.apps.api.app.services.maps.seeds import register_maps_seeds
from naas_abi.apps.nexus.apps.api.app.services.maps.settings.adapters.secondary.memory import (
    InMemoryMapsSettingsStore,
)
from naas_abi.apps.nexus.apps.api.app.services.maps.workspace_config import WorkspaceMapsDefaults
from naas_abi_core.engine.call_context import as_service_account
from naas_abi_core.services.iam.IAMPorts import PermissionDeniedError

OFFER = Offer.of(features=["maps"]).merged(platform_maps())
WORKSPACES = {"ws-1": "One", "ws-2": "Two", "ws-3": "Three", "ws-old": "Old"}
SEEDS = ("platform-a", "platform-b")


class _NoStore:
    async def managed_among(self, policy_ids):  # noqa: ANN001 - unused here
        return {}


def _feed(feed_id: str) -> MapsLayout:
    return MapsLayout(
        id=feed_id,
        title=feed_id,
        feed_type=FEED_GEOJSON_URL,
        feed_url=f"/api/maps/custom-source/{feed_id}",
    )


@pytest.fixture
def team():
    nexus = NexusIam(features_with_roles=False)
    with nexus.installed():
        nexus.grouped_org("org-1", "Acme")
        nexus.containers = {  # type: ignore[attr-defined]
            ws: nexus.grouped_workspace("org-1", ws, WORKSPACES[ws], offer=OFFER).container
            for ws in WORKSPACES
        }
        for person in ("viewer2", "member2", "admin2", "admin1", "both", "viewer3", "stranger"):
            nexus.user(person)
        nexus.platform_admin("root")
        yield nexus
    CONTAINER_DEFAULTS.forget_grouped()


@pytest_asyncio.fixture
async def world(team):
    containers = team.containers
    people = [
        *((f"{level}2", level, "ws-2") for level in ("viewer", "member", "admin")),
        ("viewer3", "viewer", "ws-3"),
        ("admin1", "admin", "ws-1"),
        ("both", "admin", "ws-1"),
        ("both", "admin", "ws-2"),
    ]
    for user, level, workspace in people:
        await MEMBERSHIPS.grant(user, level, containers[workspace])
        # The Maps feature, as the deployment's role features give it.
        team.give_features(team.principal(user), ["maps"], containers[workspace])
    # ws-old's access policy is a ceiling of an older version: no allow-list yet.
    record = CONTAINER_DEFAULTS._known[containers["ws-old"]]
    with as_service_account("api"):
        policy = team.iam.get_policy(record.access_policy_id)
        team.iam.update_policy(
            policy.id,
            expected_revision=policy.revision,
            document={
                "version": "2026-10-13",
                "statements": [
                    {
                        "sid": "Ceiling",
                        "effect": "Allow",
                        "actions": ["*"],
                        "resources": ["${scope}/*"],
                    }
                ],
            },
        )
    AUTHZ.forget_offers()

    offers = FeatureAccessService(
        EngineIamGateway(),
        _NoStore(),  # type: ignore[arg-type]
        MemoryAudit(),
        container_of=AUTHZ.container_of,
        defaults_of=CONTAINER_DEFAULTS.record_of,
        features=lambda: ["maps"],
    )
    previous = offers_runtime.configure(lambda: offers)

    grants = InMemoryMapsGrantStore()
    access = MapsAccess(grants, IamMapsOffers())
    settings = InMemoryMapsSettingsStore()
    layouts = MapsLayoutService(InMemoryMapsLayoutStore(), settings, access)
    basemaps = MapsBasemapService(InMemoryMapsBasemapStore(), settings, access)
    layers = MapsFeedLayerService(InMemoryMapsFeedLayerStore(), settings, layouts)
    # Who the route believes each one administers; IAM has the last word.
    directory = InMemoryWorkspaceDirectory(
        WORKSPACES, {"admin1": {"ws-1", "ws-3"}, "both": {"ws-1", "ws-2"}, "admin2": {"ws-2"}}
    )
    app = FastAPI()
    register_maps_seeds(app, layouts=[_feed(seed) for seed in SEEDS])
    app.include_router(layouts_api.router, prefix="/api/maps/layouts")
    app.include_router(permissions_api.router, prefix="/api/maps/permissions")
    app.dependency_overrides[layouts_api.get_maps_layout_service] = lambda: layouts
    app.dependency_overrides[layouts_api.get_maps_feed_layer_service] = lambda: layers
    app.dependency_overrides[layouts_api.maps_workspace_defaults] = WorkspaceMapsDefaults
    app.dependency_overrides[permissions_api.get_maps_access] = lambda: access
    app.dependency_overrides[permissions_api.get_maps_layout_service] = lambda: layouts
    app.dependency_overrides[permissions_api.get_maps_basemap_service] = lambda: basemaps
    app.dependency_overrides[permissions_api.get_workspace_directory] = lambda: directory
    acting_as_header(app)
    yield SimpleNamespace(nexus=team, app=app, grants=grants, access=access, offers=offers)
    offers_runtime.configure(previous)


def _offer(world, workspace: str) -> Offer:
    record = CONTAINER_DEFAULTS._known[world.nexus.containers[workspace]]
    with as_service_account("api"):
        return offer_of(world.nexus.iam.get_policy(record.access_policy_id).document)


async def _listed(world, user: str, workspace: str) -> list[str] | int:
    async with client(world.app, user) as http:
        answer = await http.get(f"/api/maps/layouts?workspace_id={workspace}")
    if answer.status_code != 200:
        return answer.status_code
    return [layout["id"] for layout in answer.json()["layouts"]]


async def _put(world, user: str, workspace: str, kind: str, item: str, **body):
    async with client(world.app, user) as http:
        return await http.put(
            f"/api/maps/permissions/{kind}/{item}?workspace_id={workspace}", json=body
        )


# -- reads follow the offer ----------------------------------------------------------------


@pytest.mark.asyncio
async def test_a_workspace_lists_the_platform_maps_its_offer_gives_alike_for_each_level(world):
    for user in ("viewer2", "member2", "admin2"):
        assert await _listed(world, user, "ws-2") == list(SEEDS), user
    assert await _listed(world, "stranger", "ws-2") == 403

    narrowed = await _put(
        world, "root", "ws-2", "layout", "platform-b", workspace_ids=["ws-1", "ws-old"]
    )
    assert narrowed.status_code == 200, narrowed.text
    assert narrowed.json()["workspace_ids"] == ["ws-1", "ws-old"]
    # Written into each workspace's offer, nothing into maps_grants.
    assert await world.grants.list(KIND_LAYOUT) == []
    assert _offer(world, "ws-2").maps_closed == {"${scope}/nexus:layout/platform-b"}
    assert _offer(world, "ws-1").maps_closed == frozenset()
    for user in ("viewer2", "member2", "admin2"):
        assert await _listed(world, user, "ws-2") == ["platform-a"], user
    assert await _listed(world, "viewer3", "ws-3") == ["platform-a"]
    assert await _listed(world, "admin1", "ws-1") == list(SEEDS)
    # Closed in ws-2: IAM refuses its copy there too.
    async with client(world.app, "viewer2") as http:
        assert (await http.get("/api/maps/layouts/platform-b?workspace_id=ws-2")).status_code in (
            403,
            404,
        )

    # ws-old is no allow-list yet: a change it would need is refused, nothing written.
    pending = await _put(world, "root", "ws-2", "layout", "platform-b", workspace_ids=["ws-1"])
    assert pending.status_code == 409, pending.text
    assert "ws-old" in pending.json()["detail"]
    assert _offer(world, "ws-1").maps_closed == frozenset()

    # Every workspace again: each offer reopens it, the read says so.
    back = await _put(world, "root", "ws-2", "layout", "platform-b", all_workspaces=True)
    assert back.status_code == 200, back.text
    assert back.json()["all_workspaces"] is True
    assert _offer(world, "ws-2").maps_closed == frozenset()
    assert await _listed(world, "viewer2", "ws-2") == list(SEEDS)


@pytest.mark.asyncio
async def test_a_workspace_with_no_allow_list_yet_goes_by_the_rows(world):
    await world.grants.save(
        MapsGrant(KIND_LAYOUT, "platform-b", DEPLOYMENT, frozenset({"ws-1"})), user_id=None
    )
    # ws-old reads the row; the others their offers, which still give it.
    assert await world.access.offers.assignment("ws-old") is None
    assert await _listed(world, "root", "ws-old") == ["platform-a"]
    assert await _listed(world, "viewer2", "ws-2") == list(SEEDS)
    async with client(world.app, "root") as http:
        listed = (await http.get("/api/maps/permissions?workspace_id=ws-1")).json()
    item = next(i for i in listed["items"] if i["item_id"] == "platform-b")
    assert item["all_workspaces"] is False
    assert item["workspace_ids"] == ["ws-1", "ws-2", "ws-3"]
    # A change that leaves ws-old as it is goes through.
    narrowed = await _put(world, "root", "ws-1", "layout", "platform-b", workspace_ids=["ws-1"])
    assert narrowed.status_code == 200, narrowed.text
    assert narrowed.json()["workspace_ids"] == ["ws-1"]


# -- writes are the caller's, IAM deciding -----------------------------------------------------


@pytest.mark.asyncio
async def test_sharing_a_feed_writes_the_other_workspaces_offer_as_the_caller(world):
    async with client(world.app, "both") as http:
        saved = await http.put(
            "/api/maps/layouts/mine?workspace_id=ws-1",
            json={
                "title": "Mine",
                "feed_type": FEED_GEOJSON_URL,
                "feed_url": "/api/maps/custom-source/mine",
                "group": "Ours",
            },
        )
    assert saved.status_code == 200, saved.text
    assert "mine" not in await _listed(world, "viewer2", "ws-2")

    shared = await _put(world, "both", "ws-1", "layout", "mine", workspace_ids=["ws-2"])
    assert shared.status_code == 200, shared.text
    assert shared.json()["workspace_ids"] == ["ws-2"]
    assert given_maps.shared_name(world.nexus.containers["ws-1"], KIND_LAYOUT, "mine") in (
        _offer(world, "ws-2").maps
    )
    for user in ("viewer2", "member2", "admin2"):
        assert "mine" in await _listed(world, user, "ws-2"), user
    async with client(world.app, "viewer2") as http:
        listed = (await http.get("/api/maps/layouts?workspace_id=ws-2")).json()["layouts"]
    assert next(layout for layout in listed if layout["id"] == "mine")["shared_from"] == "ws-1"
    assert "mine" not in await _listed(world, "viewer3", "ws-3")

    # Taken back: gone from ws-2.
    taken = await _put(world, "both", "ws-1", "layout", "mine", workspace_ids=[])
    assert taken.status_code == 200, taken.text
    assert "mine" not in await _listed(world, "viewer2", "ws-2")


@pytest.mark.asyncio
async def test_iam_refuses_a_change_the_caller_may_not_make_and_nothing_changes(world):
    async with client(world.app, "admin1") as http:
        saved = await http.put(
            "/api/maps/layouts/mine?workspace_id=ws-1",
            json={
                "title": "Mine",
                "feed_type": FEED_GEOJSON_URL,
                "feed_url": "/api/maps/custom-source/mine",
                "group": "Ours",
            },
        )
    assert saved.status_code == 200, saved.text
    before = _offer(world, "ws-3")
    # The route believes admin1 administers ws-3; IAM does not let them change its offer.
    refused = await _put(world, "admin1", "ws-1", "layout", "mine", workspace_ids=["ws-3"])
    assert refused.status_code == 403, refused.text
    assert "ws-3" in refused.json()["detail"]
    assert _offer(world, "ws-3") == before
    assert "mine" not in await _listed(world, "viewer3", "ws-3")
    # A workspace admin changes no deployment item (the route's rule, before IAM's).
    assert (
        await _put(world, "admin2", "ws-2", "layout", "platform-a", workspace_ids=[])
    ).status_code == 403
    # A member reads no access at all.
    async with client(world.app, "member2") as http:
        assert (await http.get("/api/maps/permissions?workspace_id=ws-2")).status_code == 403


@pytest.mark.asyncio
async def test_a_workspace_admin_closes_a_platform_map_and_never_reopens_it(world):
    """IAM's held rules, under the route: closing narrows (any admin of the offer), giving a
    deployment item back is the platform admin's."""
    offers = IamMapsOffers()
    await offers.change("admin2", "ws-2", KIND_LAYOUT, "platform-a", DEPLOYMENT, given=False)
    assert _offer(world, "ws-2").maps_closed == {"${scope}/nexus:layout/platform-a"}
    with pytest.raises(PermissionDeniedError):
        await offers.change("admin2", "ws-2", KIND_LAYOUT, "platform-a", DEPLOYMENT, given=True)
    assert _offer(world, "ws-2").maps_closed == {"${scope}/nexus:layout/platform-a"}
    await offers.change("root", "ws-2", KIND_LAYOUT, "platform-a", DEPLOYMENT, given=True)
    assert _offer(world, "ws-2").maps_closed == frozenset()
    # Giving a deployment item by name to a workspace given none: the platform admin's.
    record = CONTAINER_DEFAULTS._known[world.nexus.containers["ws-3"]]
    with as_service_account("api"):
        policy = world.nexus.iam.get_policy(record.access_policy_id)
        from naas_abi.apps.nexus.apps.api.app.services.iam.workspace_offer import with_offer

        world.nexus.iam.update_policy(
            policy.id,
            expected_revision=policy.revision,
            document=with_offer(
                policy.document, replace(offer_of(policy.document), maps=frozenset())
            ),
        )
    AUTHZ.forget_offers()
    await MEMBERSHIPS.grant("admin1", "admin", world.nexus.containers["ws-3"])
    world.nexus.give_features(
        world.nexus.principal("admin1"), ["maps"], world.nexus.containers["ws-3"]
    )
    with pytest.raises(PermissionDeniedError):
        await offers.change("admin1", "ws-3", KIND_LAYOUT, "platform-a", DEPLOYMENT, given=True)
    await offers.change("root", "ws-3", KIND_LAYOUT, "platform-a", DEPLOYMENT, given=True)
    assert _offer(world, "ws-3").maps == {"abi:nexus:layout/platform-a"}
    assert await _listed(world, "viewer3", "ws-3") == ["platform-a"]


@pytest.mark.asyncio
async def test_the_offer_read_says_the_maps_part_for_the_configuration(world):
    """Policy page › Configuration shows the Maps part (changed in Settings › Maps)."""
    state = await world.offers.read_offer("root", "ws-2")
    assert state["maps"] == {
        "feeds": {"every": True, "named": 0, "closed": 0, "shared": 0},
        "basemaps": {"every": True, "named": 0, "closed": 0, "shared": 0},
    }
    await _put(world, "root", "ws-2", "layout", "platform-b", workspace_ids=["ws-1", "ws-old"])
    state = await world.offers.read_offer("admin2", "ws-2")
    assert state["maps"]["feeds"] == {"every": True, "named": 0, "closed": 1, "shared": 0}
