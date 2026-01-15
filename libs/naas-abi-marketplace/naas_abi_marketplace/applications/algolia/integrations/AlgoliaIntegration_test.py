import asyncio

import pytest
from naas_abi_marketplace.applications.algolia import ABIModule
from naas_abi_marketplace.applications.algolia.integrations.AlgoliaIntegration import (
    AlgoliaIntegration,
    AlgoliaIntegrationConfiguration,
)

module = ABIModule.get_instance()
algolia_application_id = module.configuration.algolia_application_id
algolia_api_key = module.configuration.algolia_api_key


@pytest.fixture
def integration() -> AlgoliaIntegration:
    configuration = AlgoliaIntegrationConfiguration(
        app_id=algolia_application_id,
        api_key=algolia_api_key,
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
