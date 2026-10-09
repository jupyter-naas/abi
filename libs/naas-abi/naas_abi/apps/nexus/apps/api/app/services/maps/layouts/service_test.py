from __future__ import annotations

import asyncio

import pytest
from naas_abi.apps.nexus.apps.api.app.services.graph.query.port import Binding, IGraphQueryStore
from naas_abi.apps.nexus.apps.api.app.services.maps.layouts.adapters.secondary.memory import (
    InMemoryMapsLayoutStore,
)
from naas_abi.apps.nexus.apps.api.app.services.maps.layouts.layouts__schema import (
    MapsLayout,
    MapsLayoutNotFoundError,
    MapsLayoutValidationError,
)
from naas_abi.apps.nexus.apps.api.app.services.maps.layouts.service import MapsLayoutService

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
    return MapsLayoutService(InMemoryMapsLayoutStore())


def test_save_list_delete_round_trip(service: MapsLayoutService) -> None:
    asyncio.run(service.save("ws-1", _layout(), user_id="u"))

    listed = asyncio.run(service.list("ws-1"))
    assert [layout.id for layout in listed.layouts] == ["offices"]
    assert asyncio.run(service.list("ws-2")) == type(listed)(layouts=[], hidden=set())

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
    paris, other = payload["pins"]
    assert paris == {
        "id": "offices:http://ex/paris",
        "lat": 48.85,
        "lng": 2.35,
        "label": "Paris",
        "color": "#ff0000",
        "entityUri": "http://ex/paris",
    }
    assert other["detail"] == "note"
    assert "entityUri" not in other


def test_feed_caps_rows_with_a_limit(service) -> None:
    store = _Store([])

    asyncio.run(service.feed(_layout(), store))

    assert "LIMIT" in store.queries[0].upper()
