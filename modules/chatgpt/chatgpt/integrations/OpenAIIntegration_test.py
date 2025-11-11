import pytest

from src.core.chatgpt.integrations.OpenAIIntegration import (
    OpenAIIntegration, 
    OpenAIIntegrationConfiguration, 
)

@pytest.fixture
def integration() -> OpenAIIntegration:
    from src import secret
    
    configuration = OpenAIIntegrationConfiguration(
        api_key=secret.get('OPENAI_API_KEY'),
    )
    return OpenAIIntegration(configuration)

def test_list_models(integration: OpenAIIntegration):
    response = integration.list_models()
    assert response is not None, response

def test_retrieve_model(integration: OpenAIIntegration):
    response = integration.retrieve_model(model_id="gpt-4o")
    assert response is not None, response