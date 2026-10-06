"""Tests for the search's Network view: the query, what it matched, and the people."""

from __future__ import annotations

from pathlib import Path
from typing import Any

import pytest
from naas_abi_core.services.dataset.DatasetFactory import DatasetFactory
from naas_abi_core.services.dataset.DatasetService import DatasetService
from naas_abi_marketplace.domains.intelligence.modules.people.apps.people.config_loader import (
    load_config,
)
from naas_abi_marketplace.domains.intelligence.modules.people.apps.people.scripts import (
    datasets as ds,
)
from naas_abi_marketplace.domains.intelligence.modules.people.apps.people.scripts.datasets_test import (
    person_row,
)
from naas_abi_marketplace.domains.intelligence.modules.people.apps.people.scripts.network_payload import (
    find_matches,
    network,
    network_view_config,
    search_root_id,
)
from naas_abi_marketplace.domains.intelligence.modules.people.apps.people.scripts.text import (
    search_text,
)

# People of the demo graph (graphs/demo/people.ttl), as the directory lists them.
DEMO_PEOPLE = {
    "alice_dupont": ("Alice Dupont", "COO, Demo - tooling, Nexus Labs", "Demo"),
    "bob_martin": ("Bob Martin", "CEO, Demo - founded Nexus Labs", "Demo"),
    "emma_petit": ("Emma Petit", "Solo maker, LaunchPad", "LaunchPad"),
}


def _person(slug: str, name: str, headline: str, organization: str) -> dict:
    return person_row(
        slug=slug,
        full_name=name,
        headline=headline,
        organization=organization,
        about=None,
        search_text=search_text(
            {"name": [name], "headline": [headline], "organization": [organization]}
        ),
    )


@pytest.fixture
def setup(tmp_path: Path) -> tuple[DatasetService, dict[str, Any]]:
    config = load_config()
    config["data"]["namespace"] = "people"
    warehouse = DatasetFactory.DatasetServiceDuckLake(
        f"sqlite:{tmp_path / 'datasets.sqlite'}", str(tmp_path / "data")
    )
    people = [_person(slug, *values) for slug, values in DEMO_PEOPLE.items()]
    # In the directory, not in the graph: the two were built apart.
    people.append(_person("ghost_person", "Ghost Person", "Demo ghost", "Demo"))
    for logical in ds.TABLES:
        spec = ds.dataset_spec(
            logical, table=config["data"]["tables"][logical], namespace="people"
        )
        ds.replace_rows(warehouse, spec, people if logical == "people" else [])
    return warehouse, config


def _entities(view: dict, class_label: str) -> list[dict]:
    return [e for e in view["data"]["entities"] if e["classLabel"] == class_label]


def _edges(view: dict) -> set[tuple[str, str, str]]:
    return {
        (rel["from"], rel["predicateLabel"], rel["to"])
        for rel in view["data"]["relations"]
    }


def _reaches(view: dict, start: str, goal: str, hops: int) -> bool:
    """Whether ``goal`` is within ``hops`` of ``start`` on the canvas, either way."""
    frontier, seen = {start}, {start}
    for _ in range(hops):
        frontier = {
            b if a in frontier else a
            for a, _, b in _edges(view)
            if (a in frontier or b in frontier)
        } - seen
        seen |= frontier
    return goal in seen


def test_the_act_of_searching_is_the_centre(setup) -> None:
    view = network(*setup, query="Demo")
    assert view["root"] == search_root_id("Demo")
    [search] = _entities(view, "Act of Searching")
    assert search["id"] == view["root"] and search["label"] == "Demo"
    assert search["bfoBucket"] == "Process"
    assert {m["bfoBucket"] for m in _entities(view, "Search Match")} == {"GDC"}
    assert view["config"]["graph"] and view["config"]["theme"]["bfo_buckets"]


def test_the_view_opens_in_rings_without_filters_or_time() -> None:
    graph = network_view_config(load_config())["graph"]
    assert graph["layout"] == "rings"
    assert graph["temporal_filter"] is False
    assert graph["default_distance"] == 3
    assert all(not graph["view_defaults"][view]["filters"] for view in ("2d", "3d"))


def test_a_match_leads_through_what_matched_to_the_person(setup) -> None:
    view = network(*setup, query="Nexus")
    matches = _entities(view, "Search Match")
    assert {m["label"] for m in matches} >= {"Organization: Nexus Labs"}
    acts = {a["id"] for a in _entities(view, "Act of Working")}
    for match in matches:
        assert (view["root"], "has search match", match["id"]) in _edges(view)
    nexus = next(m for m in matches if m["label"] == "Organization: Nexus Labs")
    [(_, _, act)] = [e for e in _edges(view) if e[0] == nexus["id"]]
    assert act in acts
    assert any(e[1] == "has act of working" and e[2] == act for e in _edges(view))
    # search -> match -> act of working -> person: three hops, the view's distance.
    assert _reaches(view, view["root"], "Alice Dupont", 3)
    assert _reaches(view, view["root"], "Bob Martin", 3)
    # Only the acts something matched in are drawn.
    assert all(
        any(e[1] == "matches in" and e[2] == act for e in _edges(view)) for act in acts
    )


def test_a_summary_match_leads_straight_to_the_person(setup) -> None:
    view = network(*setup, query="tooling")
    [match] = _entities(view, "Search Match")
    assert match["label"] == "Summary"
    assert (match["id"], "matches in", "Alice Dupont") in _edges(view)
    text = next(p["value"] for p in match["properties"] if p["label"] == "matched text")
    assert "tooling" in text


def test_people_are_linked_to_their_profile(setup) -> None:
    view = network(*setup, query="Demo")
    alice = next(p for p in view["data"]["people"] if p["id"] == "Alice Dupont")
    assert alice["slug"] == "alice_dupont"


def test_someone_missing_from_the_graph_is_still_drawn(setup) -> None:
    view = network(*setup, query="ghost")
    assert (view["root"], "has search result", "Ghost Person") in _edges(view)


def test_no_query_ties_everyone_to_the_search(setup) -> None:
    view = network(*setup)
    assert view["total"] == 4
    for name, *_ in DEMO_PEOPLE.values():
        assert (view["root"], "has search result", name) in _edges(view)
    assert not _entities(view, "Search Match")


def test_one_client_in_three_acts_is_one_match() -> None:
    working = [
        {
            "working": f"http://ontology.naas.ai/people/ActOfWorking/{n}",
            "orgLabel": "Forvis Mazars",
            "clientLabel": "EDF R&D",
            "jobTitle": "Consultant",
        }
        for n in range(3)
    ]
    matches = find_matches(
        "Alexis Tourneux",
        ["edf"],
        working=working,
        studying=[],
        skills=[],
        summaries=[],
    )
    assert [(m["field"], m["text"]) for m in matches] == [("Client", "EDF R&D")]
    assert matches[0]["evidence"] == [f"people:ActOfWorking/{n}" for n in range(3)]
