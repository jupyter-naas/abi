import pytest
from naas_abi_marketplace.applications.google_search import ABIModule
from naas_abi_marketplace.applications.google_search.integrations.GoogleProgrammableSearchEngineIntegration import (
    GoogleProgrammableSearchEngineIntegration,
    GoogleProgrammableSearchEngineIntegrationConfiguration,
)


@pytest.fixture
def integration() -> GoogleProgrammableSearchEngineIntegration:
    module = ABIModule.get_instance()
    google_custom_search_api_key = module.configuration.google_custom_search_api_key
    google_custom_search_engine_id = module.configuration.google_custom_search_engine_id
    configuration = GoogleProgrammableSearchEngineIntegrationConfiguration(
        api_key=google_custom_search_api_key,
        search_engine_id=google_custom_search_engine_id,
    )
    return GoogleProgrammableSearchEngineIntegration(configuration)


def test_query(integration: GoogleProgrammableSearchEngineIntegration):
    results = integration.query("Florent+Ravenel+LinkedIn+profile+site:linkedin.com")
    assert results is not None, results
    assert len(results) > 0, results
    assert results[0]["title"] is not None, results[0]
    assert results[0]["link"] is not None, results[0]
    assert results[0]["snippet"] is not None, results[0]
