"""Offline tests of XSearchRecentTweetsPipeline: a saved envelope mapped into a
fake triple store (real SPARQL), through the blocking services the flows use."""

from __future__ import annotations

import asyncio
import json

import httpx
import pytest
from naas_abi_apps.common.testing import FakeTripleStore, MemoryStorage
from naas_abi_apps.x.integrations.XIntegration import (
    XIntegration,
    XIntegrationConfiguration,
)
from naas_abi_apps.x.pipelines.XSearchRecentTweetsPipeline import (
    X_GRAPH_NAME,
    XSearchRecentTweetsPipeline,
    XSearchRecentTweetsPipelineConfiguration,
    XSearchRecentTweetsPipelineParameters,
)
from naas_abi_apps.x.services import SyncService
from rdflib import RDF, Graph, Namespace, URIRef

X = Namespace("http://ontology.naas.ai/x/")
QUERY = "python lang:en"
PATH = "x/search_recent_tweets/python_lang:en/2026-07-07T14:00:06+00:00_python_lang:en.json"
ENVELOPE = {
    "query": QUERY,
    "options": {"max_results": 10, "max_pages": 1, "sort_order": "recency"},
    "results": {
        "data": [
            {
                "id": "101",
                "text": "Python 3.14 is out",
                "author_id": "1",
                "created_at": "2026-07-07T13:59:00.000Z",
                "lang": "en",
                "public_metrics": {"like_count": 3, "retweet_count": 1},
                "referenced_tweets": [{"type": "quoted", "id": "90"}],
            },
            {
                "id": "102",
                "text": "I like python",
                "author_id": "2",
                "created_at": "2026-07-07T13:58:00.000Z",
                "lang": "en",
            },
        ],
        "includes": {
            "users": [{"id": "1", "username": "alice", "name": "Alice"}],
            "tweets": [
                {"id": "101", "text": "Python 3.14 is out", "author_id": "1"},
                {"id": "90", "text": "Bientôt", "author_id": "3", "lang": "fr"},
            ],
        },
        "meta": {"newest_id": "102", "oldest_id": "101", "result_count": 2},
    },
    "started_at": "2026-07-07T14:00:05+00:00",
    "ended_at": "2026-07-07T14:00:06+00:00",
    "file_path": PATH,
}


def blocking(service: object) -> SyncService:
    """The blocking view of an async fake, as ``SyncModule`` gives the flows."""
    return SyncService(service, asyncio.run)


@pytest.fixture
def store() -> FakeTripleStore:
    return FakeTripleStore()


@pytest.fixture
def storage() -> MemoryStorage:
    storage = MemoryStorage()
    prefix, key = PATH.rsplit("/", 1)
    asyncio.run(storage.put_object(prefix, key, json.dumps(ENVELOPE).encode()))
    return storage


def pipeline(
    store: FakeTripleStore, storage: MemoryStorage, **config
) -> XSearchRecentTweetsPipeline:
    return XSearchRecentTweetsPipeline(
        XSearchRecentTweetsPipelineConfiguration(
            triple_store=blocking(store),
            object_storage=blocking(storage),
            **config,
        )
    )


def individuals(graph: Graph, class_name: str) -> set:
    return set(graph.subjects(RDF.type, X[class_name]))


def test_file_mode_maps_the_envelope_and_persists_it(store, storage) -> None:
    graph = pipeline(store, storage).run(
        XSearchRecentTweetsPipelineParameters(file_path=PATH)
    )

    assert len(individuals(graph, "SearchRecentTweets")) == 1
    assert len(individuals(graph, "SearchQuery")) == 1
    assert len(individuals(graph, "SearchResultSet")) == 1
    # Every post is an x:Tweet; the one only referenced is also x:ReferencedTweet.
    assert individuals(graph, "Tweet") == {
        X["Tweet/101"],
        X["Tweet/102"],
        X["Tweet/90"],
    }
    assert individuals(graph, "ReferencedTweet") == {X["Tweet/90"]}
    (result_set,) = individuals(graph, "SearchResultSet")
    assert set(graph.subjects(X.isContainedInSearchResultSet, result_set)) == {
        X["Tweet/101"],
        X["Tweet/102"],
    }
    assert str(graph.value(result_set, X.file_path)) == PATH
    assert store.inserts == [(X_GRAPH_NAME, len(graph))]
    # The graph is in the store, under the module's graph.
    ask = store.dataset.query(
        f"ASK {{ GRAPH <{X_GRAPH_NAME}> {{ <{X['Tweet/101']}> a <{X.Tweet}> }} }}"
    )
    assert ask.askAnswer


def test_a_second_run_does_not_emit_the_individuals_again(store, storage) -> None:
    first = pipeline(store, storage).run(
        XSearchRecentTweetsPipelineParameters(file_path=PATH)
    )
    second = pipeline(store, storage).run(
        XSearchRecentTweetsPipelineParameters(file_path=PATH, persist=False)
    )

    assert len(second) < len(first)
    assert individuals(second, "Tweet") == set()
    # Result-set membership is asserted again, never lost.
    assert len(set(second.subjects(X.isContainedInSearchResultSet, None))) == 2


def test_persist_false_writes_nothing(store, storage) -> None:
    graph = pipeline(store, storage).run(
        XSearchRecentTweetsPipelineParameters(file_path=PATH, persist=False)
    )
    assert len(graph) > 0
    assert store.inserts == []


def test_a_missing_envelope_is_an_error(store) -> None:
    with pytest.raises(FileNotFoundError):
        pipeline(store, MemoryStorage()).run(
            XSearchRecentTweetsPipelineParameters(file_path="x/missing.json")
        )


def test_the_graph_and_namespace_come_from_the_configuration(store, storage) -> None:
    graph = pipeline(
        store,
        storage,
        graph_name=URIRef("http://example.org/g"),
        namespace="http://example.org/x/",
    ).run(XSearchRecentTweetsPipelineParameters(file_path=PATH))

    assert (URIRef("http://example.org/x/Tweet/101"), RDF.type, X.Tweet) in graph
    assert store.inserts[0][0] == "http://example.org/g"


def test_query_mode_needs_the_integration(store, storage) -> None:
    with pytest.raises(ValueError, match="x_integration"):
        pipeline(store, storage).run(XSearchRecentTweetsPipelineParameters(query=QUERY))


def test_query_mode_rejects_unknown_options(store, storage) -> None:
    with pytest.raises(ValueError, match="Unknown options"):
        pipeline(store, storage).run(
            XSearchRecentTweetsPipelineParameters(
                query=QUERY, options={"not_a_real_option": True}
            )
        )


def test_query_mode_calls_the_api_through_run(store, storage) -> None:
    def api(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json=ENVELOPE["results"])

    integration = XIntegration(
        XIntegrationConfiguration(
            bearer_token="token",
            storage=storage,
            transport=httpx.MockTransport(api),
        )
    )
    graph = pipeline(store, storage, x_integration=integration, run=asyncio.run).run(
        XSearchRecentTweetsPipelineParameters(
            query=QUERY, options={"max_results": 10}, persist=False
        )
    )

    assert X["Tweet/101"] in individuals(graph, "Tweet")
    (result_set,) = individuals(graph, "SearchResultSet")
    assert str(graph.value(result_set, X.file_path)).startswith(
        "x/search_recent_tweets/python_lang:en/"
    )


def test_parameters_need_a_query_or_a_file() -> None:
    with pytest.raises(ValueError):
        XSearchRecentTweetsPipelineParameters()
