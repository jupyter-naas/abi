"""Listing the envelopes of a prefix, and the paths the graph already has."""

from __future__ import annotations

from datetime import UTC, datetime
from types import SimpleNamespace

from naas_abi_apps.x.flows.envelopes import (
    envelope_path_timestamp,
    filter_paths_by_max_age,
    list_envelope_paths,
    mapped_file_paths,
)
from rdflib import Dataset, Literal, URIRef
from rdflib.namespace import RDF

PREFIX = "x/search_recent_tweets"
OLD = "2026-10-24T10:00:00+00:00_news.json"
NEW = "2026-10-25T10:00:00+00:00_news.json"
NAMESPACE = "http://ontology.naas.ai/x/"
GRAPH = "http://ontology.naas.ai/graph/x"


class Storage:
    """The blocking object storage's ``list_objects``: direct children only."""

    def __init__(self, tree: dict[str, list[str]]) -> None:
        self.tree = tree

    def list_objects(self, prefix: str) -> list[str]:
        if prefix not in self.tree:
            raise FileNotFoundError(prefix)
        return self.tree[prefix]


STORAGE = Storage(
    {
        PREFIX: ["news/", ".nexus_folder"],
        f"{PREFIX}/news": [OLD, NEW, "notes.txt"],
    }
)


def test_every_envelope_under_the_prefix_is_listed_with_its_full_path():
    paths, skipped = list_envelope_paths(STORAGE, PREFIX)
    assert sorted(paths) == [f"{PREFIX}/news/{OLD}", f"{PREFIX}/news/{NEW}"]
    assert skipped == 0


def test_a_cutoff_keeps_the_recent_envelopes_only():
    cutoff = datetime(2026, 10, 25, tzinfo=UTC)
    paths, skipped = list_envelope_paths(STORAGE, PREFIX, cutoff=cutoff)
    assert paths == [f"{PREFIX}/news/{NEW}"] and skipped == 1
    kept, dropped = filter_paths_by_max_age(paths + ["x/no_stamp.json"], cutoff=cutoff)
    assert kept == paths and dropped == 1


def test_an_unlistable_prefix_lists_nothing():
    assert list_envelope_paths(Storage({}), PREFIX) == ([], 0)


def test_the_timestamp_of_an_envelope_comes_from_its_name():
    assert envelope_path_timestamp(NEW) == datetime(2026, 10, 25, 10, tzinfo=UTC)
    assert envelope_path_timestamp("notes.json") is None


def test_an_underscored_timestamp_keeps_its_minutes_and_seconds():
    assert envelope_path_timestamp(
        "x/search_recent_tweets/ai/2026-06-29T17_58_45+00_00_ai_llms.json"
    ) == datetime(2026, 6, 29, 17, 58, 45, tzinfo=UTC)
    assert envelope_path_timestamp(
        "x/search_recent_tweets/ai/2026-06-29T17:58:45.120000+00:00_ai_llms.json"
    ) == datetime(2026, 6, 29, 17, 58, 45, 120000, tzinfo=UTC)


def test_the_graph_lists_the_file_paths_it_mapped():
    dataset = Dataset(default_union=True)
    graph = dataset.graph(URIRef(GRAPH))
    result_set = URIRef("urn:x:rs")
    graph.add((result_set, RDF.type, URIRef(f"{NAMESPACE}SearchResultSet")))
    graph.add((result_set, URIRef(f"{NAMESPACE}file_path"), Literal("a.json")))
    triple_store = SimpleNamespace(query=dataset.query)

    assert mapped_file_paths(triple_store, GRAPH, NAMESPACE) == {"a.json"}


def test_a_graph_that_cannot_be_queried_maps_everything_again():
    def query(sparql):
        raise TimeoutError("slow")

    assert mapped_file_paths(SimpleNamespace(query=query), GRAPH, NAMESPACE) == set()
