import pytest

from src.core.modules.perplexity.integrations.PerplexityIntegration import PerplexityIntegration, PerplexityIntegrationConfiguration
from src import secret

@pytest.fixture
def perplexity_integration() -> PerplexityIntegration:
    configuration = PerplexityIntegrationConfiguration(
        api_key=secret.get("PERPLEXITY_API_KEY"),
    )
    return PerplexityIntegration(configuration)

def test_ask_question(perplexity_integration: PerplexityIntegration):
    response = perplexity_integration.search_web(
        question="What is the capital of France?",
    )
    assert response is not None
    assert "France" in response