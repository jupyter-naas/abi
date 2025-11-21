import pytest

from src.core.perplexity.integrations.PerplexityIntegration import PerplexityIntegration, PerplexityIntegrationConfiguration
from src import secret

@pytest.fixture
def perplexity_integration() -> PerplexityIntegration:
    configuration = PerplexityIntegrationConfiguration(
        api_key=secret.get("PERPLEXITY_API_KEY"),
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