"""Tests for XCountRecentTweetsPipeline: envelope → count graph mapping.

Offline: the pipeline reads a synthetic count envelope from an in-memory object
storage (``file_path`` mode, no X API call) and writes to a fake triple store
that runs real SPARQL, both through the blocking services the flows use.
"""

from __future__ import annotations

import asyncio
import json

import pytest
from naas_abi_apps.common.testing import FakeTripleStore, MemoryStorage
from naas_abi_apps.x.pipelines.XCountRecentTweetsPipeline import (
    XCountRecentTweetsPipeline,
    XCountRecentTweetsPipelineConfiguration,
    XCountRecentTweetsPipelineParameters,
)
from naas_abi_apps.x.services import SyncService
from rdflib import RDF, Graph, URIRef

_COUNT_GRAPH = "http://ontology.naas.ai/graph/x_recent_posts_count"
_NS = "http://ontology.naas.ai/x/"
_QUERY = "(openai OR anthropic) lang:en -is:retweet"
_ENVELOPE = {
    "query": _QUERY,
    "options": {
        "start_time": "2026-07-07T12:00:00Z",
        "end_time": "2026-07-07T14:00:00Z",
        "granularity": "hour",
    },
    "results": {
        "data": [
            {
                "start": "2026-07-07T12:00:00.000Z",
                "end": "2026-07-07T13:00:00.000Z",
                "tweet_count": 10,
            },
            {
                "start": "2026-07-07T13:00:00.000Z",
                "end": "2026-07-07T14:00:00.000Z",
                "tweet_count": 22,
            },
        ],
        "meta": {"total_tweet_count": 32},
    },
    "total_tweet_count": 32,
    "started_at": "2026-07-07T14:00:05Z",
    "ended_at": "2026-07-07T14:00:06Z",
    "file_path": "x/count_recent_tweets/test_pipeline/envelope.json",
}


class _TripleStore(FakeTripleStore):
    """The fake with the SDK's ``remove`` (the partial slot is replaced)."""

    async def remove(self, triples, graph_name) -> None:
        graph = self.dataset.graph(URIRef(str(graph_name)))
        for triple in triples:
            graph.remove(triple)


def _put(storage: MemoryStorage, envelope: dict) -> None:
    prefix, key = envelope["file_path"].rsplit("/", 1)
    asyncio.run(storage.put_object(prefix, key, json.dumps(envelope).encode()))


@pytest.fixture
def store() -> _TripleStore:
    return _TripleStore()


@pytest.fixture
def storage() -> MemoryStorage:
    storage = MemoryStorage()
    _put(storage, _ENVELOPE)
    return storage


@pytest.fixture
def pipeline(store: _TripleStore, storage: MemoryStorage) -> XCountRecentTweetsPipeline:
    return XCountRecentTweetsPipeline(
        XCountRecentTweetsPipelineConfiguration(
            triple_store=SyncService(store, asyncio.run),
            object_storage=SyncService(storage, asyncio.run),
            graph_name=URIRef(_COUNT_GRAPH),
        )
    )


def _count_class(graph: Graph, class_name: str) -> int:
    return len(set(graph.subjects(RDF.type, URIRef(f"{_NS}{class_name}"))))


def test_file_mode_maps_buckets_to_count_graph(pipeline: XCountRecentTweetsPipeline):
    graph = pipeline.run(
        XCountRecentTweetsPipelineParameters(
            file_path=str(_ENVELOPE["file_path"]),
            persist=False,
        )
    )

    # One process, one result set, two buckets, two intervals.
    assert _count_class(graph, "CountRecentTweets") == 1
    assert _count_class(graph, "TweetCountResultSet") == 1
    assert _count_class(graph, "TweetCountBucket") == 2
    assert _count_class(graph, "CountInterval") == 2

    # The result set carries the query string and total.
    total = [
        int(str(t)) for t in graph.objects(None, URIRef(f"{_NS}total_tweet_count"))
    ]
    assert 32 in total
    counts = sorted(
        int(str(c)) for c in graph.objects(None, URIRef(f"{_NS}bucket_tweet_count"))
    )
    assert counts == [10, 22]


def test_deterministic_bucket_uris_across_runs(pipeline: XCountRecentTweetsPipeline):
    """Re-mapping the same envelope keeps identical bucket / interval IRIs."""
    params = XCountRecentTweetsPipelineParameters(
        file_path=str(_ENVELOPE["file_path"]), persist=False
    )
    g1 = pipeline.run(params)
    g2 = pipeline.run(params)
    bucket_uris = {
        str(s) for s in g1.subjects(RDF.type, URIRef(f"{_NS}TweetCountBucket"))
    }
    # IRIs are keyed on <slug>-<bucket start>, so they are stable and query-scoped.
    assert all("TweetCountBucket/" in uri for uri in bucket_uris)
    assert len(bucket_uris) == 2
    assert bucket_uris == {
        str(s) for s in g2.subjects(RDF.type, URIRef(f"{_NS}TweetCountBucket"))
    }


def test_persisted_hours_are_not_emitted_again(
    pipeline: XCountRecentTweetsPipeline, store: _TripleStore
):
    params = XCountRecentTweetsPipelineParameters(file_path=_ENVELOPE["file_path"])
    first = pipeline.run(params)
    second = pipeline.run(params)

    assert store.inserts[0] == (_COUNT_GRAPH, len(first))
    assert _count_class(second, "TweetCountBucket") == 0
    assert _count_class(second, "CountInterval") == 0


def test_a_partial_hour_replaces_the_previous_one(
    pipeline: XCountRecentTweetsPipeline, store: _TripleStore, storage: MemoryStorage
):
    def partial(
        count: int, end: str, name: str
    ) -> XCountRecentTweetsPipelineParameters:
        envelope = {
            **_ENVELOPE,
            "options": {**_ENVELOPE["options"], "end_time": end},
            "results": {
                "data": [
                    {
                        "start": "2026-07-07T14:00:00.000Z",
                        "end": "2026-07-07T15:00:00.000Z",
                        "tweet_count": count,
                    }
                ],
                "meta": {"total_tweet_count": count},
            },
            "total_tweet_count": count,
            "file_path": f"x/count_recent_tweets/test_pipeline/{name}.json",
        }
        _put(storage, envelope)
        return XCountRecentTweetsPipelineParameters(
            file_path=envelope["file_path"], partial=True, partial_end=end
        )

    pipeline.run(partial(4, "2026-07-07T14:12:00Z", "p1"))
    pipeline.run(partial(9, "2026-07-07T14:37:00Z", "p2"))

    rows = list(
        store.dataset.query(
            f"""
            PREFIX x: <{_NS}>
            SELECT ?count ?end WHERE {{
              GRAPH <{_COUNT_GRAPH}> {{
                ?bucket x:bucket_tweet_count ?count ; x:hasCountInterval ?i .
                ?i x:bucket_end ?end .
                FILTER(STRENDS(STR(?i), "-partial"))
              }}
            }}
            """
        )
    )
    assert [(int(r[0]), str(r[1])[:16]) for r in rows] == [(9, "2026-07-07T14:37")]


def test_query_mode_needs_the_integration(pipeline: XCountRecentTweetsPipeline):
    with pytest.raises(ValueError, match="x_integration"):
        pipeline.run(XCountRecentTweetsPipelineParameters(query=_QUERY))
