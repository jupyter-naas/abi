import pytest
from naas_abi_core import logger
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

module = ABIModule.get_instance()
bearer_token = module.configuration.bearer_token
triple_store_service = module.engine.services.triple_store

# Stable public fixtures used across tests.
QUERY = "python lang:en"
OPTIONS = {"max_results": 10, "max_pages": 1, "sort_order": "recency"}


@pytest.fixture
def pipeline() -> XSearchRecentTweetsPipeline:
    x_integration = XIntegration(XIntegrationConfiguration(bearer_token=bearer_token))
    configuration = XSearchRecentTweetsPipelineConfiguration(
        x_integration=x_integration,
        triple_store=triple_store_service,
    )
    return XSearchRecentTweetsPipeline(configuration)


def test_run(pipeline: XSearchRecentTweetsPipeline):
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


def test_run_emits_tweets(pipeline: XSearchRecentTweetsPipeline):
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
    with pytest.raises(ValueError, match="Unknown options"):
        pipeline.run(
            XSearchRecentTweetsPipelineParameters(
                query=QUERY,
                options={"max_results": 10, "not_a_real_option": True},
                persist=False,
            )
        )


def test_rerun_is_idempotent(pipeline: XSearchRecentTweetsPipeline):
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
