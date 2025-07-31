import pytest

from src.custom.modules.perplexity.integrations.PerplexityIntegration import PerplexityIntegration, PerplexityIntegrationConfiguration
from src import secret

@pytest.fixture
def perplexity_integration() -> PerplexityIntegration:
    configuration = PerplexityIntegrationConfiguration(
        api_key=secret.get("PERPLEXITY_API_KEY"),
    )
    return PerplexityIntegration(configuration)

def test_ask_question(perplexity_integration: PerplexityIntegration):
    response = perplexity_integration.ask_question(
        question="What is the capital of France?",
    )
    assert response is not None
    assert "France" in response