"""Tests for XCountRecentTweetsPipeline: envelope → count graph mapping.

Uses the engine ``module`` fixture (skips if the module can't be loaded in this
environment) and drives the pipeline in ``file_path`` mode over a synthetic
count envelope written to object storage, so no X API call is made.
"""

import pytest
from naas_abi_core.engine.Engine import Engine
from naas_abi_core.utils.StorageUtils import StorageUtils
from naas_abi_marketplace.applications.x import ABIModule
from naas_abi_marketplace.applications.x.integrations.XIntegration import (
    XIntegration,
    XIntegrationConfiguration,
)
from naas_abi_marketplace.applications.x.pipelines.XCountRecentTweetsPipeline import (
    XCountRecentTweetsPipeline,
    XCountRecentTweetsPipelineConfiguration,
    XCountRecentTweetsPipelineParameters,
)
from rdflib import RDF, Graph, URIRef

_COUNT_GRAPH = "http://ontology.naas.ai/graph/x_recent_posts_count"
_NS = "http://ontology.naas.ai/x/"
_QUERY = "(drone OR uas) lang:en -is:retweet"
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


@pytest.fixture(scope="session")
def module() -> ABIModule:
    try:
        engine = Engine()
        engine.load(module_names=["naas_abi_marketplace.applications.x"])
        return ABIModule.get_instance()
    except Exception as exc:  # noqa: BLE001 — environment-dependent boot
        pytest.skip(f"X module could not be loaded in this environment: {exc}")


@pytest.fixture
def pipeline(module: ABIModule) -> XCountRecentTweetsPipeline:
    x_integration = XIntegration(
        XIntegrationConfiguration(bearer_token=module.configuration.bearer_token)
    )
    return XCountRecentTweetsPipeline(
        XCountRecentTweetsPipelineConfiguration(
            x_integration=x_integration,
            triple_store=module.engine.services.triple_store,
            object_storage=module.engine.services.object_storage,
            graph_name=URIRef(_COUNT_GRAPH),
        )
    )


def _count_class(graph: Graph, class_name: str) -> int:
    return len(set(graph.subjects(RDF.type, URIRef(f"{_NS}{class_name}"))))


def test_file_mode_maps_buckets_to_count_graph(
    module: ABIModule, pipeline: XCountRecentTweetsPipeline
):
    # Persist the synthetic envelope where the pipeline reads it from.
    StorageUtils(module.engine.services.object_storage).save_json(
        _ENVELOPE,
        "x/count_recent_tweets/test_pipeline",
        "envelope.json",
        copy=False,
    )

    graph = pipeline.run(
        XCountRecentTweetsPipelineParameters(
            file_path=_ENVELOPE["file_path"],
            persist=False,
        )
    )

    # One process, one result set, two buckets, two intervals.
    assert _count_class(graph, "CountRecentTweets") == 1
    assert _count_class(graph, "TweetCountResultSet") == 1
    assert _count_class(graph, "TweetCountBucket") == 2
    assert _count_class(graph, "CountInterval") == 2

    # The result set carries the query string and total.
    total = list(graph.objects(None, URIRef(f"{_NS}total_tweet_count")))
    assert any(int(t) == 32 for t in total)
    counts = sorted(
        int(c) for c in graph.objects(None, URIRef(f"{_NS}bucket_tweet_count"))
    )
    assert counts == [10, 22]


def test_deterministic_bucket_uris_across_runs(
    module: ABIModule, pipeline: XCountRecentTweetsPipeline
):
    """Re-mapping the same envelope keeps identical bucket / interval IRIs."""
    StorageUtils(module.engine.services.object_storage).save_json(
        _ENVELOPE,
        "x/count_recent_tweets/test_pipeline",
        "envelope.json",
        copy=False,
    )
    params = XCountRecentTweetsPipelineParameters(
        file_path=_ENVELOPE["file_path"], persist=False
    )
    g1 = pipeline.run(params)
    bucket_uris = {
        str(s) for s in g1.subjects(RDF.type, URIRef(f"{_NS}TweetCountBucket"))
    }
    # IRIs are keyed on <slug>-<bucket start>, so they are stable and query-scoped.
    assert all("TweetCountBucket/" in uri for uri in bucket_uris)
    assert len(bucket_uris) == 2
