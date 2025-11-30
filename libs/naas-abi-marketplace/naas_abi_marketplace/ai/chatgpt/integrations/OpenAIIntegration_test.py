import pytest
from naas_abi_marketplace.ai.chatgpt import ABIModule
from naas_abi_marketplace.ai.chatgpt.integrations.OpenAIIntegration import (
    OpenAIIntegration,
    OpenAIIntegrationConfiguration,
)


@pytest.fixture
def integration(module: ABIModule) -> OpenAIIntegration:
    configuration = OpenAIIntegrationConfiguration(
        api_key=module.configuration.openai_api_key,
    )
    return OpenAIIntegration(configuration)


def test_list_models(integration: OpenAIIntegration):
    response = integration.list_models()
    assert response is not None, response


def test_retrieve_model(integration: OpenAIIntegration):
    response = integration.retrieve_model(model_id="gpt-4o")
    assert response is not None, response
