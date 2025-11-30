import pytest
from naas_abi_marketplace.applications.openrouter.integrations.OpenRouterAPIIntegration import (
    OpenRouterAPIIntegration,
    OpenRouterAPIIntegrationConfiguration,
)


@pytest.fixture
def integration() -> OpenRouterAPIIntegration:
    from naas_abi import secret

    configuration = OpenRouterAPIIntegrationConfiguration(
        api_key=secret.get("OPENROUTER_API_KEY")
    )
    return OpenRouterAPIIntegration(configuration)


def test_create_response(integration: OpenRouterAPIIntegration):
    result = integration.create_response(
        input_prompt="What is the capital of France?",
        tools=[],
        model="openai/gpt-4.1-mini",
        temperature=0.7,
        top_p=0.9,
    )
    assert isinstance(result, dict)


def test_get_user_activity(integration: OpenRouterAPIIntegration):
    result = integration.get_user_activity()
    assert isinstance(result, dict)


def test_get_remaining_credits(integration: OpenRouterAPIIntegration):
    result = integration.get_remaining_credits()
    assert isinstance(result, dict)


def test_list_all_models(integration: OpenRouterAPIIntegration):
    result = integration.list_all_models()
    assert isinstance(result, dict)


def test_list_providers(integration: OpenRouterAPIIntegration):
    result = integration.list_providers()
    assert isinstance(result, dict)


def test_list_api_keys(integration: OpenRouterAPIIntegration):
    result = integration.list_api_keys()
    assert isinstance(result, dict)


def test_get_current_api_key(integration: OpenRouterAPIIntegration):
    result = integration.get_current_api_key()
    assert isinstance(result, dict)
