import asyncio

import pytest
from naas_abi_marketplace.applications.algolia.integrations.AlgoliaIntegration import (
    AlgoliaIntegration,
    AlgoliaIntegrationConfiguration,
)


@pytest.fixture
def integration() -> AlgoliaIntegration:
    from naas_abi import secret

    configuration = AlgoliaIntegrationConfiguration(
        app_id=secret.get("ALGOLIA_APPLICATION_ID"),
        api_key=secret.get("ALGOLIA_API_KEY"),
    )
    return AlgoliaIntegration(configuration)


def test_search(integration: AlgoliaIntegration):
    index_name = "workspace-search"
    query = "Finance"
    hits_per_page = 1
    filters = "type:ontology AND category:class"
    results = asyncio.run(
        integration.search(
            index_name=index_name,
            query=query,
            hits_per_page=hits_per_page,
            filters=filters,
        )
    )

    assert len(results) > 0, results
    assert results[0][1][0] is not None, results
