import pytest
from naas_abi_marketplace.ai.perplexity.integrations.PerplexityIntegration import (
    PerplexityIntegration,
    PerplexityIntegrationConfiguration,
)


@pytest.fixture
def perplexity_integration() -> PerplexityIntegration:
    from naas_abi_marketplace.ai.perplexity import ABIModule

    module = ABIModule.get_instance()
    perplexity_api_key = module.configuration.perplexity_api_key

    configuration = PerplexityIntegrationConfiguration(
        api_key=perplexity_api_key,
    )
    return PerplexityIntegration(configuration)


def test_perplexity_quick_search(perplexity_integration: PerplexityIntegration):
    response = perplexity_integration.search_web(
        question="What is the capital of France?",
        user_location="FR",
        search_context_size="medium",
        model="sonar",
    )
    assert response is not None
    assert "France" in response


def test_perplexity_search(perplexity_integration: PerplexityIntegration):
    response = perplexity_integration.search_web(
        question="What is the capital of France?",
        user_location="FR",
        search_context_size="medium",
        model="sonar-pro",
    )
    assert response is not None
    assert "France" in response


def test_perplexity_advanced_search(perplexity_integration: PerplexityIntegration):
    response = perplexity_integration.search_web(
        question="What is the capital of France?",
        user_location="FR",
        search_context_size="high",
        model="sonar-pro",
    )
    assert response is not None
    assert "France" in response
