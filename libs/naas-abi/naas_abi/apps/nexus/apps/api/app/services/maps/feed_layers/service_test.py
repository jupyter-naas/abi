from __future__ import annotations

import asyncio

import pytest
from naas_abi.apps.nexus.apps.api.app.services.maps.feed_layers.adapters.secondary.memory import (
    InMemoryMapsFeedLayerStore,
)
from naas_abi.apps.nexus.apps.api.app.services.maps.feed_layers.feed_layers__schema import (
    MapsFeedLayer,
    MapsFeedLayerNotFoundError,
    MapsFeedLayerPolicyError,
    MapsFeedLayerValidationError,
)
from naas_abi.apps.nexus.apps.api.app.services.maps.feed_layers.service import (
    MapsFeedLayerService,
)
from naas_abi.apps.nexus.apps.api.app.services.maps.layouts.adapters.secondary.memory import (
    InMemoryMapsLayoutStore,
)
from naas_abi.apps.nexus.apps.api.app.services.maps.layouts.layouts__schema import (
    FEED_GEOJSON_URL,
    MapsLayout,
    MapsLayoutPolicyError,
)
from naas_abi.apps.nexus.apps.api.app.services.maps.layouts.service import MapsLayoutService
from naas_abi.apps.nexus.apps.api.app.services.maps.permissions.adapters.secondary.memory import (
    InMemoryMapsGrantStore,
)
from naas_abi.apps.nexus.apps.api.app.services.maps.permissions.permissions__schema import (
    DEPLOYMENT,
    KIND_LAYOUT,
)
from naas_abi.apps.nexus.apps.api.app.services.maps.permissions.service import (
    MapsAccess,
    MapsActor,
)
from naas_abi.apps.nexus.apps.api.app.services.maps.settings.adapters.secondary.memory import (
    InMemoryMapsSettingsStore,
)

SUPER = MapsActor("root", True, frozenset({"ws-1", "ws-2"}))


def _feed(feed_id: str, **overrides) -> MapsLayout:
    values = {
        "id": feed_id,
        "title": feed_id.upper(),
        "feed_type": FEED_GEOJSON_URL,
        "feed_url": f"/api/maps/organization-facilities/{feed_id}",
        "color": "#001a70",
    }
    values.update(overrides)
    return MapsLayout(**values)


EDF = _feed("edf")
EDF_LAYERS = [
    MapsFeedLayer(
        id="edf-solar",
        feed_id="edf",
        title="Solar",
        color="#e85130",
        icon="Sun",
        class_labels=("Solar",),
    ),
    MapsFeedLayer(
        id="edf-hydro",
        feed_id="edf",
        title="Hydro",
        icon="Droplets",
        class_labels=("Hydro", "Hydro (planned)"),
    ),
]


class _Env:
    def __init__(self) -> None:
        self.access = MapsAccess(InMemoryMapsGrantStore())
        self.settings = InMemoryMapsSettingsStore()
        self.feeds = MapsLayoutService(InMemoryMapsLayoutStore(), self.settings, self.access)
        self.layers = MapsFeedLayerService(InMemoryMapsFeedLayerStore(), self.settings, self.feeds)

    def list(self, ws: str, seeds=()) -> list[MapsFeedLayer]:
        asyncio.run(self.feeds.list(ws, seeds=[EDF]))
        return asyncio.run(self.layers.list(ws, seeds=seeds))


@pytest.fixture
def env() -> _Env:
    return _Env()


def test_a_new_feed_gets_one_layer_with_its_id(env) -> None:
    asyncio.run(env.feeds.save("ws-1", _feed("acme", title="Acme", color="#123456"), user_id="u"))
    layers = env.list("ws-1")
    acme = next(layer for layer in layers if layer.feed_id == "acme")
    assert (acme.id, acme.title, acme.color, acme.class_labels) == ("acme", "Acme", "#123456", ())


def test_seeded_feed_gets_its_seeded_layers(env) -> None:
    layers = [layer for layer in env.list("ws-1", seeds=EDF_LAYERS) if layer.feed_id == "edf"]
    assert [(layer.id, layer.system) for layer in layers] == [
        ("edf-hydro", True),
        ("edf-solar", True),
    ]
    # Not re-created once the workspace has layers on the feed.
    assert len(env.list("ws-1", seeds=EDF_LAYERS)) == 2


def test_layer_crud_and_the_last_layer_rule(env) -> None:
    asyncio.run(env.feeds.save("ws-1", _feed("acme"), user_id="u"))
    env.list("ws-1")
    offices = MapsFeedLayer(
        id="acme-offices",
        feed_id="acme",
        title=" Offices ",
        color="#ff0000",
        class_labels=("Office", "Office", " "),
    )
    saved = asyncio.run(env.layers.save("ws-1", offices, user_id="u"))
    assert saved.title == "Offices" and saved.class_labels == ("Office",)
    asyncio.run(
        env.layers.save(
            "ws-1",
            MapsFeedLayer(**{**offices.to_dict(), "class_labels": ("Office",), "title": "Sites"}),
            user_id="u",
        )
    )
    assert asyncio.run(env.layers.get("ws-1", "acme-offices")).title == "Sites"

    asyncio.run(env.layers.delete("ws-1", "acme"))  # the default layer: another one remains
    with pytest.raises(MapsFeedLayerPolicyError):
        asyncio.run(env.layers.delete("ws-1", "acme-offices"))  # last layer of the feed
    with pytest.raises(MapsFeedLayerValidationError):
        asyncio.run(
            env.layers.save("ws-1", MapsFeedLayer(id="x", feed_id="nope", title="X"), user_id="u")
        )
    with pytest.raises(MapsFeedLayerValidationError):
        asyncio.run(
            env.layers.save(
                "ws-1", MapsFeedLayer(id="acme-offices", feed_id="edf", title="Moved"), user_id="u"
            )
        )
    with pytest.raises(MapsFeedLayerValidationError):
        asyncio.run(
            env.layers.save(
                "ws-1",
                MapsFeedLayer(id="earthquakes", feed_id="acme", title="X"),
                user_id="u",
                reserved={"earthquakes"},
            )
        )


def test_seeded_layers_cannot_be_deleted(env) -> None:
    env.list("ws-1", seeds=EDF_LAYERS)
    with pytest.raises(MapsFeedLayerPolicyError):
        asyncio.run(env.layers.delete("ws-1", "edf-solar"))
    # ...but can be edited, keeping the flag.
    edited = asyncio.run(
        env.layers.save(
            "ws-1",
            MapsFeedLayer(id="edf-solar", feed_id="edf", title="Sun", color="#ffaa00"),
            user_id="u",
        )
    )
    assert edited.system


def test_deleting_a_feed_deletes_its_layers(env) -> None:
    asyncio.run(env.feeds.save("ws-1", _feed("acme"), user_id="u"))
    env.list("ws-1")
    asyncio.run(env.feeds.set_hidden("ws-1", "acme", True, user_id="u"))
    asyncio.run(env.layers.delete_feed("ws-1", "acme"))
    assert [layer.feed_id for layer in env.list("ws-1")] == ["edf"]
    assert asyncio.run(env.settings.get("ws-1")).hidden_layouts == frozenset()
    with pytest.raises(MapsLayoutPolicyError):
        asyncio.run(env.layers.delete_feed("ws-1", "edf"))  # seeded feed


def test_layers_follow_their_feed_access(env) -> None:
    env.list("ws-1", seeds=EDF_LAYERS)
    asyncio.run(
        env.access.update(
            KIND_LAYOUT,
            "edf",
            DEPLOYMENT,
            all_workspaces=False,
            workspace_ids={"ws-2"},
            actor=SUPER,
        )
    )
    assert env.list("ws-1", seeds=EDF_LAYERS) == []
    with pytest.raises(MapsFeedLayerNotFoundError):
        asyncio.run(env.layers.get("ws-1", "edf-solar"))
    assert {layer.id for layer in env.list("ws-2", seeds=EDF_LAYERS)} == {"edf-solar", "edf-hydro"}


def test_shared_feed_brings_its_layers_read_only(env) -> None:
    asyncio.run(env.feeds.save("ws-1", _feed("acme"), user_id="u"))
    asyncio.run(
        env.access.update(
            KIND_LAYOUT, "acme", "ws-1", all_workspaces=False, workspace_ids={"ws-2"}, actor=SUPER
        )
    )
    shared = next(layer for layer in env.list("ws-2") if layer.feed_id == "acme")
    assert shared.shared_from == "ws-1"
    with pytest.raises(MapsFeedLayerPolicyError):
        asyncio.run(env.layers.delete("ws-2", shared.id))
    with pytest.raises(MapsFeedLayerPolicyError):
        asyncio.run(
            env.layers.save(
                "ws-2", MapsFeedLayer(id="mine", feed_id="acme", title="Mine"), user_id="u"
            )
        )


def test_a_seed_revision_migrates_existing_workspaces(env) -> None:
    """Bumping the revision re-applies seeds; a seeded feed drops its automatic default."""
    acme = _feed("acme", system=False)
    asyncio.run(env.feeds.ensure_seeded("ws-1", [acme], {"acme": 1}))
    # First deploy: no layer seeds → the default "every feature" layer.
    asyncio.run(env.feeds.list("ws-1"))
    assert [
        layer.id for layer in asyncio.run(env.layers.list("ws-1")) if layer.feed_id == "acme"
    ] == ["acme"]

    offices = MapsFeedLayer(
        id="acme", feed_id="acme", title="Offices", class_labels=("Office",), color="#fe5815"
    )
    poles = MapsFeedLayer(id="acme-power", feed_id="acme", title="Power", class_labels=("Power",))
    layers = asyncio.run(
        env.layers.list("ws-1", seeds=[offices, poles], revisions={"acme": 2, "acme-power": 2})
    )
    by_id = {layer.id: layer for layer in layers if layer.feed_id == "acme"}
    assert by_id["acme"].title == "Offices" and by_id["acme"].class_labels == ("Office",)
    assert set(by_id) == {"acme", "acme-power"}

    # Same revision again: an admin's edit stays.
    asyncio.run(
        env.layers.save(
            "ws-1",
            MapsFeedLayer(id="acme", feed_id="acme", title="Sites", class_labels=("Office",)),
            user_id="u",
        )
    )
    again = asyncio.run(
        env.layers.list("ws-1", seeds=[offices, poles], revisions={"acme": 2, "acme-power": 2})
    )
    assert next(layer for layer in again if layer.id == "acme").title == "Sites"


def test_seeds_replace_the_automatic_default_layer(env) -> None:
    env.list("ws-1")  # EDF seeded with its default layer (no layer seeds yet)
    assert [layer.id for layer in env.list("ws-1")] == ["edf"]
    asyncio.run(env.feeds.set_hidden("ws-1", "edf", True, user_id="u"))
    layers = env.list("ws-1", seeds=EDF_LAYERS)
    assert {layer.id for layer in layers} == {"edf-solar", "edf-hydro"}
    assert "edf" not in asyncio.run(env.settings.get("ws-1")).hidden_layouts
