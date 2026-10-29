"""Connections served from datasets: the count, the Connections tab, its network.

A people graph (the demo directory) and two users' LinkedIn graphs, built by the
LinkedIn connections pipeline, are materialized into a real DuckLake warehouse
and read back the way the app reads a workspace: ``filter_graph_iris`` for the
order, ``load_store`` for the merge.
"""

from __future__ import annotations

from typing import Any

import pytest
from naas_abi_core.services.dataset.DatasetFactory import DatasetFactory
from naas_abi_core.services.dataset.DatasetService import DatasetService
from naas_abi_marketplace.applications.linkedin.integrations.LinkedInExportIntegration import (
    read_connections_csv,
)
from naas_abi_marketplace.applications.linkedin.pipelines.ActOfConnectionsOnLinkedInExportPipeline import (
    ActOfConnectionsOnLinkedInExportPipeline,
    ActOfConnectionsOnLinkedInExportPipelineConfiguration,
    ActOfConnectionsOnLinkedInExportPipelineParameters,
    KnownPerson,
)
from naas_abi_marketplace.domains.intelligence.modules.people.apps.people.config_loader import (
    load_config,
)
from naas_abi_marketplace.domains.intelligence.modules.people.apps.people.scripts import (
    connections_payload as cp,
)
from naas_abi_marketplace.domains.intelligence.modules.people.apps.people.scripts import (
    graph_datasets as gd,
)
from naas_abi_marketplace.domains.intelligence.modules.people.apps.people.scripts import (
    search_payload,
)
from naas_abi_marketplace.domains.intelligence.modules.people.apps.people.scripts.export_people_from_graph import (
    connection_rows,
)
from naas_abi_marketplace.domains.intelligence.modules.people.apps.people.scripts.people_resolver import (
    filter_graph_iris,
)
from naas_abi_marketplace.domains.intelligence.modules.people.utils.paths import (
    DEMO_GRAPH_FILE,
)
from rdflib import Graph

PEOPLE = "http://ontology.naas.ai/graph/people/demo"
ALICE_LINKEDIN = "http://ontology.naas.ai/graph/user-alice/linkedin"
CAROL_LINKEDIN = "http://ontology.naas.ai/graph/user-carol/linkedin"
BOB = "http://ontology.naas.ai/abi/Person/bob-martin"

HEADER = b"First Name,Last Name,URL,Email Address,Company,Position,Connected On\n"
ALICE_CSV = HEADER + (
    b"Bob,Martin,https://www.linkedin.com/in/bob-martin-demo,,Demo,CEO,02 Feb 2020\n"
    b"Jane,Doe,https://www.linkedin.com/in/jane-doe,,AXA,Chief Risk Officer,23 Oct 2025\n"
    b"John,Smith,https://www.linkedin.com/in/john-smith,,EDF,Engineer,01 Jan 2024\n"
)
CAROL_CSV = HEADER + (
    b"Jane,Doe,https://www.linkedin.com/in/jane-doe,,AXA,Chief Risk Officer,05 Mar 2023\n"
    b"Marc,Roux,https://www.linkedin.com/in/marc-roux,,AXA,Actuary,01 Jun 2022\n"
)


def _linkedin_graph(owner: str, name: str, slug: str, csv: bytes) -> Graph:
    pipeline = ActOfConnectionsOnLinkedInExportPipeline(
        ActOfConnectionsOnLinkedInExportPipelineConfiguration()
    )
    graph, _ = pipeline.build(
        ActOfConnectionsOnLinkedInExportPipelineParameters(
            owner_uri=owner,
            owner_name=name,
            owner_slug=slug,
            rows=read_connections_csv(csv),
            source_path=f"uploads/linkedin/{slug}/Connections.csv",
            known_people={
                "https://www.linkedin.com/in/bob-martin-demo": KnownPerson(
                    uri=BOB, slug="bob_martin"
                )
            },
        )
    )
    return graph


@pytest.fixture(scope="module")
def config() -> dict[str, Any]:
    config = load_config()
    config["data"]["graph"]["include_prefixes"] = [
        "http://ontology.naas.ai/graph/people/"
    ]
    config["data"]["graph"]["supplementary_suffixes"] = ["/linkedin"]
    return config


@pytest.fixture(scope="module")
def store(tmp_path_factory: pytest.TempPathFactory, config: dict[str, Any]):
    tmp_path = tmp_path_factory.mktemp("connections")
    warehouse: DatasetService = DatasetFactory.DatasetServiceDuckLake(
        f"sqlite:{tmp_path / 'datasets.sqlite'}", str(tmp_path / "data")
    )
    demo = Graph().parse(DEMO_GRAPH_FILE, format="turtle")
    gd.materialize_graph(warehouse, config, PEOPLE, demo)
    gd.materialize_graph(
        warehouse,
        config,
        ALICE_LINKEDIN,
        _linkedin_graph(
            "http://ontology.naas.ai/abi/Person/alice-dupont",
            "Alice Dupont",
            "alice_dupont",
            ALICE_CSV,
        ),
    )
    gd.materialize_graph(
        warehouse,
        config,
        CAROL_LINKEDIN,
        _linkedin_graph(
            "http://ontology.naas.ai/abi/Person/carol-owner",
            "Carol Owner",
            "carol_owner",
            CAROL_CSV,
        ),
    )
    iris = filter_graph_iris(
        frozenset({CAROL_LINKEDIN, PEOPLE, ALICE_LINKEDIN}), config
    )
    return gd.load_store(
        warehouse, config, [gd.graph_namespace(config, iri) for iri in iris]
    )


def test_linkedin_graphs_are_read_after_the_people_graphs(config) -> None:
    readable = frozenset(
        {
            "http://ontology.naas.ai/graph/0000-user/linkedin",
            PEOPLE,
            "http://ontology.naas.ai/graph/other",
        }
    )
    assert filter_graph_iris(readable, config) == [
        PEOPLE,
        "http://ontology.naas.ai/graph/0000-user/linkedin",
    ]


def test_connection_rows_are_both_directions_with_the_earliest_date() -> None:
    rows = connection_rows(
        [
            {"ownerSlug": "a", "slug": "b", "connectedOn": "2024-05-01"},
            {"ownerSlug": "b", "slug": "a", "connectedOn": "2020-01-01"},
            {"ownerSlug": "a", "slug": "a", "connectedOn": "2020-01-01"},
        ]
    )
    assert rows == [
        {"slug": "a", "peer_slug": "b", "connected_on": "2020-01-01"},
        {"slug": "b", "peer_slug": "a", "connected_on": "2020-01-01"},
    ]


def test_a_person_in_several_datasets_appears_once(store, config) -> None:
    payload = search_payload.search(store, config, query="", facet="", page=1)
    slugs = [result["slug"] for result in payload["results"]]
    assert len(slugs) == len(set(slugs))
    assert "li_jane_doe" in slugs
    # Bob is in the people graph and in Alice's export: listed from the
    # people graph, which is read first.
    bob = next(
        result for result in payload["results"] if result["slug"] == "bob_martin"
    )
    assert bob["headline"] != "CEO"


def test_search_results_carry_their_connection_count(store, config) -> None:
    payload = search_payload.search(store, config, query="", facet="", page=1)
    counts = {
        result["slug"]: result["connections_count"] for result in payload["results"]
    }
    assert counts["alice_dupont"] == 3
    # Connected to Alice and to Carol, from two exports.
    assert counts["li_jane_doe"] == 2
    assert counts["bob_martin"] == 1
    assert counts["emma_petit"] == 0


def test_sorted_by_connections_drops_the_unconnected(store, config) -> None:
    payload = search_payload.search(
        store, config, query="", facet="", page=1, sort="connections"
    )
    counts = [result["connections_count"] for result in payload["results"]]
    assert counts and all(counts)
    assert counts == sorted(counts, reverse=True)
    assert payload["results"][0]["slug"] == "alice_dupont"
    assert payload["total"] == len(counts)
    assert "emma_petit" not in {result["slug"] for result in payload["results"]}


def test_the_connections_of_a_person_with_organization_position_and_date(
    store, config
) -> None:
    payload = cp.connections(store, config, slug="alice_dupont")
    assert payload["total"] == 3
    first = payload["results"][0]
    assert first == {
        **first,
        "slug": "li_jane_doe",
        "organization": "AXA",
        "position": "Chief Risk Officer",
        "connected_on": "2025-10-23",
        "connections_count": 2,
    }
    # Most connected first, then most recent.
    order = [
        (-item["connections_count"], item["connected_on"])
        for item in payload["results"]
    ]
    assert [count for count, _ in order] == sorted(count for count, _ in order)
    for (count, date), (next_count, next_date) in zip(order, order[1:]):
        if count == next_count:
            assert date >= next_date


def test_a_connection_two_exports_share_lists_both_owners(store, config) -> None:
    payload = cp.connections(store, config, slug="li_jane_doe")
    assert {item["slug"] for item in payload["results"]} == {
        "alice_dupont",
        "carol_owner",
    }


def test_an_unknown_person_is_not_found(store, config) -> None:
    with pytest.raises(cp.PersonNotFoundError):
        cp.connections(store, config, slug="nobody")


def _relations(view, predicate):
    return [
        relation
        for relation in view["data"]["relations"]
        if relation["predicateUri"] == predicate
    ]


def _entities(view, class_uri):
    return {
        entity["id"]: entity
        for entity in view["data"]["entities"]
        if entity["classUri"] == class_uri
    }


def test_the_connections_network_is_the_person_and_their_connections_only(
    store, config
) -> None:
    view = cp.connections_network(store, config, slug="alice_dupont")
    drawn = {person["slug"] for person in view["data"]["people"]}
    assert drawn == {"alice_dupont", "li_jane_doe", "li_john_smith", "bob_martin"}


def test_each_connection_is_an_act_both_people_take_part_in(store, config) -> None:
    view = cp.connections_network(store, config, slug="alice_dupont")
    acts = _entities(view, cp.CONNECTION_CLASS)
    assert len(acts) == 3
    assert all(act["bfoBucket"] == "Process" for act in acts.values())
    participants: dict[str, set[str]] = {}
    for relation in _relations(view, "abi:hasParticipant"):
        participants.setdefault(relation["from"], set()).add(relation["to"])
    assert set(participants) == set(acts)
    assert all(
        view["root"] in pair and len(pair) == 2 for pair in participants.values()
    )
    jane = next(act for act in acts.values() if "Jane Doe" in str(act["properties"]))
    assert jane["startedAt"] == "2025-10-23"


def test_colleagues_meet_at_their_organization_through_their_acts_of_working(
    store, config
) -> None:
    view = cp.connections_network(store, config, slug="carol_owner")
    workings = _entities(view, "abi:ActOfWorking")
    organizations = _entities(view, "abi:Organization")
    assert set(organizations) == {"organization:axa"}
    worked_by = {
        relation["from"]: relation["to"]
        for relation in _relations(view, "abi:hasActOfWorking")
    }
    assert set(worked_by) == {"Jane Doe", "Marc Roux"}
    assert set(worked_by.values()) == set(workings)
    for_org = {
        relation["from"]: relation["to"]
        for relation in _relations(view, "abi:forOrganization")
    }
    assert for_org == {act: "organization:axa" for act in workings}
    # No shortcut from a person straight to the organization.
    assert not _relations(view, "abi:worksFor")
