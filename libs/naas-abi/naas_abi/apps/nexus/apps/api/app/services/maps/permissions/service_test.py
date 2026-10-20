from __future__ import annotations

import asyncio

import pytest
from naas_abi.apps.nexus.apps.api.app.services.maps.basemaps.adapters.secondary.memory import (
    InMemoryMapsBasemapStore,
)
from naas_abi.apps.nexus.apps.api.app.services.maps.basemaps.basemaps__schema import (
    MapsBasemap,
    MapsBasemapNotFoundError,
    MapsBasemapPolicyError,
    MapsBasemapPreview,
)
from naas_abi.apps.nexus.apps.api.app.services.maps.basemaps.service import MapsBasemapService
from naas_abi.apps.nexus.apps.api.app.services.maps.layouts.adapters.secondary.memory import (
    InMemoryMapsLayoutStore,
)
from naas_abi.apps.nexus.apps.api.app.services.maps.layouts.layouts__schema import (
    FEED_GEOJSON_URL,
    MapsLayout,
    MapsLayoutNotFoundError,
    MapsLayoutPolicyError,
    MapsLayoutValidationError,
)
from naas_abi.apps.nexus.apps.api.app.services.maps.layouts.service import MapsLayoutService
from naas_abi.apps.nexus.apps.api.app.services.maps.permissions.adapters.secondary.memory import (
    InMemoryMapsGrantStore,
)
from naas_abi.apps.nexus.apps.api.app.services.maps.permissions.permissions__schema import (
    DEPLOYMENT,
    KIND_BASEMAP,
    KIND_LAYOUT,
    MapsPermissionError,
)
from naas_abi.apps.nexus.apps.api.app.services.maps.permissions.service import (
    MapsAccess,
    MapsActor,
)
from naas_abi.apps.nexus.apps.api.app.services.maps.settings.adapters.secondary.memory import (
    InMemoryMapsSettingsStore,
)

SUPER = MapsActor("root", True, frozenset({"ws-fm", "ws-fr", "ws-valeo", "ws-other"}))
FR_ADMIN = MapsActor("fr", False, frozenset({"ws-fr", "ws-valeo"}))


def _feed(layer_id: str, **overrides) -> MapsLayout:
    values = {
        "id": layer_id,
        "title": layer_id,
        "feed_type": FEED_GEOJSON_URL,
        "feed_url": f"/api/maps/organization-facilities/{layer_id}",
    }
    values.update(overrides)
    return MapsLayout(**values)


SEEDS = [_feed("forvis-mazars-facilities"), _feed("valeo-facilities")]


@pytest.fixture
def access() -> MapsAccess:
    return MapsAccess(InMemoryMapsGrantStore())


@pytest.fixture
def layouts(access) -> MapsLayoutService:
    return MapsLayoutService(InMemoryMapsLayoutStore(), InMemoryMapsSettingsStore(), access)


def _ids(service: MapsLayoutService, workspace_id: str) -> list[str]:
    return [layout.id for layout in asyncio.run(service.list(workspace_id, seeds=SEEDS)).layouts]


def test_deployment_layers_everywhere_until_restricted(access, layouts) -> None:
    """The brief's example: Forvis everywhere, Valeo on two workspaces only."""
    assert _ids(layouts, "ws-other") == ["forvis-mazars-facilities", "valeo-facilities"]

    asyncio.run(
        access.update(
            KIND_LAYOUT,
            "valeo-facilities",
            DEPLOYMENT,
            all_workspaces=False,
            workspace_ids={"ws-fr", "ws-valeo"},
            actor=SUPER,
        )
    )

    for ws in ("ws-fr", "ws-valeo"):
        assert _ids(layouts, ws) == ["forvis-mazars-facilities", "valeo-facilities"]
    # Already seeded elsewhere: filtered out, and unreachable by id (feed proxy).
    assert _ids(layouts, "ws-other") == ["forvis-mazars-facilities"]
    assert _ids(layouts, "ws-new") == ["forvis-mazars-facilities"]
    with pytest.raises(MapsLayoutNotFoundError):
        asyncio.run(layouts.get("ws-other", "valeo-facilities"))
    # Its id stays reserved there.
    with pytest.raises(MapsLayoutValidationError):
        asyncio.run(layouts.save("ws-other", _feed("valeo-facilities"), user_id="u"))

    # Re-opened to all: back (and seeded where it never was).
    asyncio.run(
        access.update(
            KIND_LAYOUT,
            "valeo-facilities",
            DEPLOYMENT,
            all_workspaces=True,
            workspace_ids=set(),
            actor=SUPER,
        )
    )
    assert "valeo-facilities" in _ids(layouts, "ws-new")


def test_only_superadmins_change_deployment_items_or_share_everywhere(access) -> None:
    with pytest.raises(MapsPermissionError):
        asyncio.run(
            access.update(
                KIND_LAYOUT,
                "x",
                DEPLOYMENT,
                all_workspaces=False,
                workspace_ids={"ws-fr"},
                actor=FR_ADMIN,
            )
        )
    with pytest.raises(MapsPermissionError):
        asyncio.run(
            access.update(
                KIND_LAYOUT, "x", "ws-fr", all_workspaces=True, workspace_ids=set(), actor=FR_ADMIN
            )
        )


def test_custom_layers_are_shared_read_only(access, layouts) -> None:
    asyncio.run(layouts.save("ws-fr", _feed("fr-offices", color="#112233"), user_id="u"))
    assert "fr-offices" not in _ids(layouts, "ws-valeo")

    asyncio.run(
        access.update(
            KIND_LAYOUT,
            "fr-offices",
            "ws-fr",
            all_workspaces=False,
            workspace_ids={"ws-valeo"},
            actor=FR_ADMIN,
        )
    )
    shared = asyncio.run(layouts.get("ws-valeo", "fr-offices"))
    assert shared.shared_from == "ws-fr"
    assert "fr-offices" not in _ids(layouts, "ws-other")

    with pytest.raises(MapsLayoutPolicyError):
        asyncio.run(layouts.save("ws-valeo", _feed("fr-offices"), user_id="u"))
    with pytest.raises(MapsLayoutPolicyError):
        asyncio.run(layouts.delete("ws-valeo", "fr-offices"))
    # Hiding and recoloring stay local.
    asyncio.run(layouts.set_hidden("ws-valeo", "fr-offices", True, user_id="u"))
    asyncio.run(layouts.set_color("ws-valeo", "fr-offices", "#abcdef", user_id="u"))
    listed = asyncio.run(layouts.list("ws-valeo"))
    local = next(layout for layout in listed.layouts if layout.id == "fr-offices")
    assert local.color == "#abcdef" and listed.hidden == {"fr-offices"}
    assert asyncio.run(layouts.get("ws-fr", "fr-offices")).color == "#112233"

    # Deleting at home drops the share.
    asyncio.run(layouts.delete("ws-fr", "fr-offices"))
    assert asyncio.run(access.policy(KIND_LAYOUT)).grants == {}
    assert "fr-offices" not in _ids(layouts, "ws-valeo")


def test_non_superadmin_only_touches_administered_workspaces(access) -> None:
    asyncio.run(
        access.update(
            KIND_LAYOUT,
            "fr-offices",
            "ws-fr",
            all_workspaces=False,
            workspace_ids={"ws-other"},
            actor=SUPER,
        )
    )
    with pytest.raises(MapsPermissionError) as exc_info:
        # Removing ws-other, which FR_ADMIN does not administer.
        asyncio.run(
            access.update(
                KIND_LAYOUT,
                "fr-offices",
                "ws-fr",
                all_workspaces=False,
                workspace_ids={"ws-valeo"},
                actor=FR_ADMIN,
            )
        )
    assert "ws-other" in str(exc_info.value)

    grant = asyncio.run(
        access.update(
            KIND_LAYOUT,
            "fr-offices",
            "ws-fr",
            all_workspaces=False,
            workspace_ids={"ws-other", "ws-valeo"},
            actor=FR_ADMIN,
        )
    )
    assert grant.workspace_ids == {"ws-other", "ws-valeo"}


def test_back_to_default_policy_removes_the_row(access) -> None:
    store = InMemoryMapsGrantStore()
    access = MapsAccess(store)
    asyncio.run(
        access.update(
            KIND_LAYOUT, "a", DEPLOYMENT, all_workspaces=False, workspace_ids={"ws-fr"}, actor=SUPER
        )
    )
    asyncio.run(
        access.update(
            KIND_LAYOUT, "a", DEPLOYMENT, all_workspaces=True, workspace_ids=set(), actor=SUPER
        )
    )
    asyncio.run(
        access.update(
            KIND_LAYOUT, "b", "ws-fr", all_workspaces=False, workspace_ids={"ws-fr"}, actor=SUPER
        )
    )
    assert asyncio.run(store.list(KIND_LAYOUT)) == []


def test_shared_basemap_preview_comes_from_its_owner(access) -> None:
    svg = b'<svg xmlns="http://www.w3.org/2000/svg"/>'
    service = MapsBasemapService(InMemoryMapsBasemapStore(), InMemoryMapsSettingsStore(), access)
    asyncio.run(
        service.save(
            "ws-fr",
            MapsBasemap(id="emea", title="EMEA", renderer={"kind": "countries"}),
            user_id="u",
        )
    )
    asyncio.run(service.set_preview("ws-fr", "emea", "image/svg+xml", svg, user_id="u"))

    with pytest.raises(MapsBasemapNotFoundError):
        asyncio.run(service.get_preview("ws-valeo", "emea"))
    asyncio.run(
        access.update(
            KIND_BASEMAP,
            "emea",
            "ws-fr",
            all_workspaces=False,
            workspace_ids={"ws-valeo"},
            actor=SUPER,
        )
    )
    assert asyncio.run(service.get_preview("ws-valeo", "emea")) == MapsBasemapPreview(
        "image/svg+xml", svg
    )
    assert asyncio.run(service.list("ws-valeo")).basemaps[0].shared_from == "ws-fr"
    with pytest.raises(MapsBasemapPolicyError):
        asyncio.run(service.set_preview("ws-valeo", "emea", "image/svg+xml", svg, user_id="u"))
    with pytest.raises(MapsBasemapPolicyError):
        asyncio.run(service.delete("ws-valeo", "emea"))


def test_restricted_deployment_basemap_is_not_seeded(access) -> None:
    service = MapsBasemapService(InMemoryMapsBasemapStore(), InMemoryMapsSettingsStore(), access)
    seed = (
        MapsBasemap(
            id="group", title="Group", category="organization", renderer={"kind": "countries"}
        ),
        None,
    )
    asyncio.run(
        access.update(
            KIND_BASEMAP,
            "group",
            DEPLOYMENT,
            all_workspaces=False,
            workspace_ids={"ws-fr"},
            actor=SUPER,
        )
    )
    assert [b.id for b in asyncio.run(service.list("ws-other", seeds=[seed])).basemaps] == []
    assert [b.id for b in asyncio.run(service.list("ws-fr", seeds=[seed])).basemaps] == ["group"]
