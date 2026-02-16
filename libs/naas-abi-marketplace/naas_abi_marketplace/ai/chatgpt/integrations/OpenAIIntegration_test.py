import pytest

from naas_abi_marketplace.ai.chatgpt.integrations.OpenAIIntegration import (
    OpenAIIntegration,
    OpenAIIntegrationConfiguration,
)


@pytest.fixture
def integration() -> OpenAIIntegration:
    from naas_abi_core.engine.Engine import Engine
    from naas_abi_marketplace.ai.chatgpt import ABIModule

    engine = Engine()
    engine.load(module_names=["naas_abi_marketplace.ai.chatgpt"])

    module = ABIModule.get_instance()
    openai_api_key = module.configuration.openai_api_key

    configuration = OpenAIIntegrationConfiguration(
        api_key=openai_api_key,
    )
    return OpenAIIntegration(configuration)


def test_list_models(integration: OpenAIIntegration):
    response = integration.list_models()
    assert response is not None, response


def test_retrieve_model(integration: OpenAIIntegration):
    response = integration.retrieve_model(model_id="gpt-4.1-mini")
    assert response is not None, response


def test_create_chat_completion(integration: OpenAIIntegration):
    response = integration.create_chat_completion(
        prompt="What is the capital of France?",
        model="gpt-4.1-mini",
        temperature=0.3,
    )
    assert response is not None, response
    assert "Paris" in response["content"], response


def test_create_chat_completion_o3_mini(integration: OpenAIIntegration):
    response = integration.create_chat_completion(
        messages=[
            {"role": "user", "content": "What is the capital of France?"},
        ],
        model="o3-mini",
        temperature=0.3,
    )
    assert response is not None, response
    assert "Paris" in response["content"], response
