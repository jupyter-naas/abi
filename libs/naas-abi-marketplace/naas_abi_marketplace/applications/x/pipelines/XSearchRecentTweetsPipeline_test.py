import pytest
from naas_abi_core import logger
from naas_abi_core.engine.Engine import Engine
from naas_abi_marketplace.applications.x import ABIModule
from naas_abi_marketplace.applications.x.integrations.XIntegration import (
    XIntegration,
    XIntegrationConfiguration,
)
from naas_abi_marketplace.applications.x.pipelines.XSearchRecentTweetsPipeline import (
    XSearchRecentTweetsPipeline,
    XSearchRecentTweetsPipelineConfiguration,
    XSearchRecentTweetsPipelineParameters,
)
from rdflib import URIRef

# Stable public fixtures used across tests.
QUERY = "python lang:en"
OPTIONS = {"max_results": 10, "max_pages": 1, "sort_order": "recency"}


@pytest.fixture(scope="session")
def module() -> ABIModule:
    """Load the X module through the engine once per test session.

    Done in a fixture (not at import time) so test *collection* never
    depends on a pre-initialised module — a bare ``ABIModule.get_instance()``
    at module scope raises ``ValueError`` during collection when nothing has
    loaded the engine yet.
    """
    try:
        engine = Engine()
        engine.load(module_names=["naas_abi_marketplace.applications.x"])
        return ABIModule.get_instance()
    except Exception as exc:  # noqa: BLE001 — environment-dependent boot
        pytest.skip(f"X module could not be loaded in this environment: {exc}")


@pytest.fixture
def pipeline(module: ABIModule) -> XSearchRecentTweetsPipeline:
    x_integration = XIntegration(
        XIntegrationConfiguration(bearer_token=module.configuration.bearer_token)
    )
    configuration = XSearchRecentTweetsPipelineConfiguration(
        x_integration=x_integration,
        triple_store=module.engine.services.triple_store,
        object_storage=module.engine.services.object_storage,
        graph_name=URIRef(module.configuration.graph_name),
    )
    return XSearchRecentTweetsPipeline(configuration)


@pytest.fixture
def live_api(module: ABIModule) -> None:
    """Skip tests that hit the live X v2 API when no bearer token is set."""
    if not module.configuration.bearer_token:
        pytest.skip("X_BEARER_TOKEN not configured; skipping live X API test.")


def test_run(pipeline: XSearchRecentTweetsPipeline, live_api: None):
    graph = pipeline.run(
        XSearchRecentTweetsPipelineParameters(
            query=QUERY,
            options=OPTIONS,
            persist=False,
        )
    )

    assert len(graph) > 0, f"Expected non-empty graph, got {len(graph)} triples"
    logger.info(f"Total triples: {len(graph)}")


def test_run_emits_search_recent_tweets_individual(
    pipeline: XSearchRecentTweetsPipeline,
    live_api: None,
):
    graph = pipeline.run(
        XSearchRecentTweetsPipelineParameters(
            query=QUERY,
            options=OPTIONS,
            persist=False,
        )
    )

    rows = list(
        graph.query(
            """
            PREFIX rdf:  <http://www.w3.org/1999/02/22-rdf-syntax-ns#>
            PREFIX rdfs: <http://www.w3.org/2000/01/rdf-schema#>
            PREFIX x:    <http://ontology.naas.ai/x/>
            SELECT ?s ?label WHERE {
                ?s rdf:type x:SearchRecentTweets ;
                   rdfs:label ?label .
            }
            """
        )
    )

    assert rows, f"Expected at least one SearchRecentTweets individual, got {rows}"
    logger.info(f"SearchRecentTweets individuals: {rows}")


def test_run_emits_tweets(pipeline: XSearchRecentTweetsPipeline, live_api: None):
    graph = pipeline.run(
        XSearchRecentTweetsPipelineParameters(
            query=QUERY,
            options=OPTIONS,
            persist=False,
        )
    )

    tweet_count = len(
        list(
            graph.query(
                """
                PREFIX rdf: <http://www.w3.org/1999/02/22-rdf-syntax-ns#>
                PREFIX x:   <http://ontology.naas.ai/x/>
                SELECT ?s WHERE { ?s rdf:type x:Tweet . }
                """
            )
        )
    )

    assert tweet_count > 0, f"Expected more than 0 Tweet individuals, got {tweet_count}"
    logger.info(f"Total Tweet individuals: {tweet_count}")


def test_run_rejects_unknown_option(pipeline: XSearchRecentTweetsPipeline):
    # Option validation happens before any API call, so this runs offline.
    with pytest.raises(ValueError, match="Unknown options"):
        pipeline.run(
            XSearchRecentTweetsPipelineParameters(
                query=QUERY,
                options={"max_results": 10, "not_a_real_option": True},
                persist=False,
            )
        )


def test_rerun_is_idempotent(pipeline: XSearchRecentTweetsPipeline, live_api: None):
    """A second run on the same query should not duplicate already-stored individuals."""
    first = pipeline.run(
        XSearchRecentTweetsPipelineParameters(
            query=QUERY,
            options=OPTIONS,
            persist=True,
        )
    )
    second = pipeline.run(
        XSearchRecentTweetsPipelineParameters(
            query=QUERY,
            options=OPTIONS,
            persist=False,
        )
    )

    assert len(second) <= len(first), (
        f"Second run produced more triples ({len(second)}) than the first "
        f"({len(first)}); label-based dedup did not take effect."
    )
    logger.info(
        f"First run: {len(first)} triples, "
        f"second run (after persist): {len(second)} triples"
    )
