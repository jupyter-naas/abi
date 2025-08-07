import pytest

from src.core.modules.chatgpt.integrations.OpenAIWebSearchIntegration import (
    OpenAIWebSearchIntegration, 
    OpenAIWebSearchIntegrationConfiguration, 
)

@pytest.fixture
def integration() -> OpenAIWebSearchIntegration:
    from src import secret
    
    configuration = OpenAIWebSearchIntegrationConfiguration(
        api_key=secret.get('OPENAI_API_KEY'),
    )
    return OpenAIWebSearchIntegration(configuration)

def test_web_search(integration: OpenAIWebSearchIntegration):
    query = "What is the capital of France?"
    response = integration.search_web(query=query, search_context_size="medium")
    import rich

    rich.inspect(response)
    rich.print(f'Output text: {response[0].get("content")[0].get("text")}')

    assert response is not None, response
    assert response[0].get("status") == "completed", response[0]
    assert "Paris" in response[0].get("content")[0].get("text"), response[0].get("content")[0].get("text")