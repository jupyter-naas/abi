from __future__ import annotations

import asyncio

import pytest
from naas_abi.apps.nexus.apps.api.app.services.graph.query.port import Binding, IGraphQueryStore
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
from naas_abi.apps.nexus.apps.api.app.services.maps.settings.adapters.secondary.memory import (
    InMemoryMapsSettingsStore,
)

QUERY = """
PREFIX ex: <http://example.org/>
SELECT ?uri ?label ?lat ?lng WHERE { ?uri ex:name ?label ; ex:lat ?lat ; ex:lng ?lng . }
"""


def _layout(**overrides) -> MapsLayout:
    values = {"id": "offices", "title": "Offices", "query": QUERY}
    values.update(overrides)
    return MapsLayout(**values)


class _Store(IGraphQueryStore):
    def __init__(self, rows):
        self.rows = rows
        self.queries: list[str] = []

    def select(self, sparql):
        self.queries.append(sparql)
        return self.rows

    def count(self, sparql):
        return len(self.rows)

    def supports_fulltext(self):
        return False


def _row(**cells):
    return {k: Binding(str(v), k == "uri") for k, v in cells.items()}


@pytest.fixture
def service() -> MapsLayoutService:
    return MapsLayoutService(InMemoryMapsLayoutStore(), InMemoryMapsSettingsStore())


def test_save_list_delete_round_trip(service: MapsLayoutService) -> None:
    asyncio.run(service.save("ws-1", _layout(), user_id="u"))

    listed = asyncio.run(service.list("ws-1"))
    assert [layout.id for layout in listed.layouts] == ["offices"]
    assert asyncio.run(service.list("ws-2")) == type(listed)(layouts=[], hidden=set(), colors={})

    asyncio.run(service.delete("ws-1", "offices"))
    assert (asyncio.run(service.list("ws-1"))).layouts == []
    with pytest.raises(MapsLayoutNotFoundError):
        asyncio.run(service.delete("ws-1", "offices"))


@pytest.mark.parametrize(
    ("overrides", "message"),
    [
        ({"id": "Bad Id"}, "id"),
        ({"title": "  "}, "title"),
        ({"query": "DELETE WHERE { ?s ?p ?o }"}, "SPARQL"),
        ({"query": "ASK WHERE { ?s ?p ?o }"}, "SELECT"),
        ({"query": "SELECT ?label WHERE { ?s ?p ?label }"}, "?lat"),
        (
            {"query": "SELECT ?label ?lat ?lng WHERE { SERVICE <http://x> { ?s ?p ?label } }"},
            "SERVICE",
        ),
        (
            {"query": "SELECT ?label ?lat ?lng FROM <http://g> WHERE { ?s ?p ?label }"},
            "FROM",
        ),
        ({"color": "red"}, "color"),
    ],
)
def test_save_rejects_invalid_layouts(service, overrides, message) -> None:
    with pytest.raises(MapsLayoutValidationError) as exc_info:
        asyncio.run(service.save("ws-1", _layout(**overrides), user_id="u"))
    assert any(message in error for error in exc_info.value.errors), exc_info.value.errors


def test_builtin_ids_cannot_be_taken_by_custom_layouts(service) -> None:
    with pytest.raises(MapsLayoutValidationError):
        asyncio.run(
            service.save("ws-1", _layout(id="earthquakes"), user_id="u", reserved={"earthquakes"})
        )


def test_visibility_is_per_workspace(service) -> None:
    asyncio.run(service.set_hidden("ws-1", "earthquakes", True, user_id="u"))
    asyncio.run(service.set_hidden("ws-1", "offices", True, user_id="u"))
    asyncio.run(service.set_hidden("ws-1", "offices", False, user_id="u"))

    assert (asyncio.run(service.list("ws-1"))).hidden == {"earthquakes"}
    assert (asyncio.run(service.list("ws-2"))).hidden == set()


def test_feeds_are_switched_off_apart_from_layers(service) -> None:
    asyncio.run(service.set_feed_hidden("ws-1", "offices", True, user_id="u"))
    asyncio.run(service.set_feed_hidden("ws-1", "earthquakes", True, user_id="u"))
    asyncio.run(service.set_feed_hidden("ws-1", "earthquakes", False, user_id="u"))

    listed = asyncio.run(service.list("ws-1"))
    assert listed.hidden_feeds == {"offices"}
    # A layer with the feed's id keeps its own flag.
    assert listed.hidden == set()
    assert asyncio.run(service.list("ws-2")).hidden_feeds == set()
    with pytest.raises(MapsLayoutValidationError):
        asyncio.run(service.set_feed_hidden("ws-1", "Not An Id", True, user_id="u"))


def test_feeds_are_switched_in_bulk(service) -> None:
    asyncio.run(service.set_feeds_hidden("ws-1", ["a", "b", "c"], True, user_id="u"))
    assert asyncio.run(service.set_feeds_hidden("ws-1", ["a", "c", "zz"], False, user_id="u")) == {
        "b"
    }
    with pytest.raises(MapsLayoutValidationError):
        asyncio.run(service.set_feeds_hidden("ws-1", ["ok", "Bad Id"], True, user_id="u"))
    assert asyncio.run(service.list("ws-1")).hidden_feeds == {"b"}


def test_deleting_a_feed_forgets_its_switch(service) -> None:
    asyncio.run(service.save("ws-1", _layout(), user_id="u"))
    asyncio.run(service.set_feed_hidden("ws-1", "offices", True, user_id="u"))

    asyncio.run(service.delete("ws-1", "offices"))

    assert asyncio.run(service.list("ws-1")).hidden_feeds == set()


def test_deleting_a_layout_forgets_its_hidden_flag(service) -> None:
    asyncio.run(service.save("ws-1", _layout(), user_id="u"))
    asyncio.run(service.set_hidden("ws-1", "offices", True, user_id="u"))

    asyncio.run(service.delete("ws-1", "offices"))

    assert (asyncio.run(service.list("ws-1"))).hidden == set()


def test_feed_turns_rows_into_pins_and_skips_bad_coordinates(service) -> None:
    store = _Store(
        [
            _row(uri="http://ex/paris", label="Paris", lat="48.85", lng="2.35"),
            _row(label="No uri", lat="10", lng="20", detail="note"),
            _row(uri="http://ex/bad", label="Bad", lat="abc", lng="2"),
            _row(uri="http://ex/far", label="Out of range", lat="95", lng="2"),
        ]
    )

    payload = asyncio.run(service.feed(_layout(color="#ff0000"), store))

    assert payload["count"] == 2
    assert payload["type"] == "FeatureCollection"
    paris, other = payload["features"]
    assert paris == {
        "type": "Feature",
        "id": "offices:http://ex/paris",
        "geometry": {"type": "Point", "coordinates": [2.35, 48.85]},
        "properties": {
            "label": "Paris",
            "color": "#ff0000",
            "entityUri": "http://ex/paris",
        },
    }
    assert other["properties"]["detail"] == "note"
    assert "entityUri" not in other["properties"]


def test_feed_caps_rows_with_a_limit(service) -> None:
    store = _Store([])

    asyncio.run(service.feed(_layout(), store))

    assert "LIMIT" in store.queries[0].upper()


def _feed(**overrides) -> MapsLayout:
    values = {
        "id": "acme-facilities",
        "title": "Acme",
        "feed_type": FEED_GEOJSON_URL,
        "feed_url": "/api/maps/organization-facilities/acme-facilities",
        "group": "Organizations Facilities",
        "logo_url": "/api/organizations/logos/Acme/Acme.ico",
        "color": "#171c8f",
    }
    values.update(overrides)
    return MapsLayout(**values)


def test_feed_layers_need_a_same_host_api_path(service) -> None:
    saved = asyncio.run(service.save("ws-1", _feed(query="ignored"), user_id="u"))
    assert saved.query == "" and saved.feed_url.startswith("/api/")

    for bad in ("https://evil.example/x", "//evil.example/x", "/api/../admin", "/other/x", ""):
        with pytest.raises(MapsLayoutValidationError) as exc_info:
            asyncio.run(service.save("ws-1", _feed(feed_url=bad), user_id="u"))
        assert any("feed_url" in e for e in exc_info.value.errors)


def test_feed_layer_logo_and_group_are_checked(service) -> None:
    with pytest.raises(MapsLayoutValidationError) as exc_info:
        asyncio.run(
            service.save("ws-1", _feed(logo_url="javascript:alert(1)", group=" "), user_id="u")
        )
    assert any("logo_url" in e for e in exc_info.value.errors)
    assert any("group" in e for e in exc_info.value.errors)

    with pytest.raises(MapsLayoutValidationError) as exc_info:
        asyncio.run(service.save("ws-1", _feed(group="x" * 81), user_id="u"))
    assert any("group" in e for e in exc_info.value.errors)


def test_group_is_a_free_label(service) -> None:
    saved = asyncio.run(service.save("ws-1", _feed(group="Field Offices"), user_id="u"))
    assert saved.group == "Field Offices"
    assert saved.to_dict()["group"] == "Field Offices" and "category" not in saved.to_dict()


@pytest.mark.parametrize(
    ("record", "group"),
    [
        ({"category": "public"}, "Public"),
        ({"category": "environment"}, "Environment"),
        ({"category": "organizations-facility"}, "Organizations Facilities"),
        ({"category": "user-field-offices"}, "user-field-offices"),
        ({"category": ""}, "Custom"),
        ({}, "Custom"),
        ({"group": "Partners", "category": "public"}, "Partners"),
    ],
)
def test_legacy_category_records_read_as_groups(record, group) -> None:
    assert MapsLayout.from_dict({"id": "x", "title": "X", **record}).group == group


def test_seeds_are_copied_once_and_cannot_be_deleted(service) -> None:
    seed = _feed()
    first = asyncio.run(service.list("ws-1", seeds=[seed]))
    assert [(layout.id, layout.system) for layout in first.layouts] == [("acme-facilities", True)]

    # Edits survive later lists; the request cannot drop the system flag.
    asyncio.run(service.save("ws-1", _feed(title="Acme sites", system=False), user_id="u"))
    again = asyncio.run(service.list("ws-1", seeds=[seed]))
    assert [(layout.title, layout.system) for layout in again.layouts] == [("Acme sites", True)]

    with pytest.raises(MapsLayoutPolicyError):
        asyncio.run(service.delete("ws-1", "acme-facilities"))

    hidden = asyncio.run(service.set_hidden("ws-1", "acme-facilities", True, user_id="u"))
    assert hidden == {"acme-facilities"}


def test_seed_removed_from_store_is_not_recreated(service) -> None:
    store = InMemoryMapsLayoutStore()
    settings = InMemoryMapsSettingsStore()
    service = MapsLayoutService(store, settings)
    asyncio.run(service.list("ws-1", seeds=[_feed()]))
    asyncio.run(store.delete("ws-1", "acme-facilities"))

    assert asyncio.run(service.list("ws-1", seeds=[_feed()])).layouts == []


def test_layer_colors_for_records_and_builtins(service) -> None:
    asyncio.run(service.save("ws-1", _layout(), user_id="u"))

    colors = asyncio.run(service.set_color("ws-1", "earthquakes", "#123456", user_id="u"))
    assert colors == {"earthquakes": "#123456"}
    asyncio.run(service.set_color("ws-1", "offices", "#abcdef", user_id="u"))

    listed = asyncio.run(service.list("ws-1"))
    assert listed.colors == {"earthquakes": "#123456"}
    assert listed.layouts[0].color == "#abcdef"

    assert asyncio.run(service.set_color("ws-1", "earthquakes", None, user_id="u")) == {}
    with pytest.raises(MapsLayoutValidationError):
        asyncio.run(service.set_color("ws-1", "offices", "blue", user_id="u"))


def test_hidden_flags_keep_other_settings(service) -> None:
    settings = InMemoryMapsSettingsStore()
    service = MapsLayoutService(InMemoryMapsLayoutStore(), settings)
    asyncio.run(service.set_color("ws-1", "earthquakes", "#123456", user_id="u"))
    asyncio.run(service.set_hidden("ws-1", "earthquakes", True, user_id="u"))

    stored = asyncio.run(settings.get("ws-1"))
    assert stored.layer_colors == {"earthquakes": "#123456"}
    assert stored.hidden_layouts == {"earthquakes"}


def test_feed_layers_do_not_run_sparql(service) -> None:
    with pytest.raises(MapsLayoutValidationError):
        asyncio.run(service.feed(_feed(), _Store([])))


def test_hidden_seeds_hide_once_per_revision(service) -> None:
    listed = asyncio.run(service.list("ws-1", hidden_seeds={"earthquakes": 1, "news": 1}))
    assert listed.hidden == {"earthquakes", "news"}

    # An admin can show a layer again; the same revision does not hide it twice.
    asyncio.run(service.set_hidden("ws-1", "news", False, user_id="u"))
    again = asyncio.run(service.list("ws-1", hidden_seeds={"earthquakes": 1, "news": 1}))
    assert again.hidden == {"earthquakes"}

    # A higher revision re-applies it (a deployment migration).
    bumped = asyncio.run(service.list("ws-1", hidden_seeds={"earthquakes": 1, "news": 2}))
    assert bumped.hidden == {"earthquakes", "news"}
    assert asyncio.run(service.list("ws-2")).hidden == set()


def test_hidden_feed_seeds_switch_feeds_off_once_per_revision(service) -> None:
    seeds = {"earthquakes": 1, "iss": 1}
    listed = asyncio.run(service.list("ws-1", hidden_feed_seeds=seeds))
    assert listed.hidden_feeds == {"earthquakes", "iss"}
    assert listed.hidden == set()

    # An admin enables one again: the same revision leaves it on.
    asyncio.run(service.set_feed_hidden("ws-1", "iss", False, user_id="u"))
    assert asyncio.run(service.list("ws-1", hidden_feed_seeds=seeds)).hidden_feeds == {
        "earthquakes"
    }
    bumped = asyncio.run(service.list("ws-1", hidden_feed_seeds={"earthquakes": 1, "iss": 2}))
    assert bumped.hidden_feeds == {"earthquakes", "iss"}
