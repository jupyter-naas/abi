import pytest
from naas_abi_marketplace.ai.chatgpt.integrations.OpenAIResponsesIntegration import (
    OpenAIResponsesIntegration,
    OpenAIResponsesIntegrationConfiguration,
)


@pytest.fixture
def integration() -> OpenAIResponsesIntegration:
    from naas_abi_core.engine.Engine import Engine
    from naas_abi_marketplace.ai.chatgpt import ABIModule

    engine = Engine()
    engine.load(module_names=["naas_abi_marketplace.ai.chatgpt"])

    module = ABIModule.get_instance()
    openai_api_key = module.configuration.openai_api_key

    configuration = OpenAIResponsesIntegrationConfiguration(
        api_key=openai_api_key,
    )
    return OpenAIResponsesIntegration(configuration)


def test_web_search(integration: OpenAIResponsesIntegration):
    from datetime import datetime

    query = """
    What's the news today? You must start your response with the date in the format YYYY-MM-DD.
    Example: Here are the news of the day: 2025-09-25: ...
    """
    response = integration.search_web(
        query=query,
        search_context_size="medium",
        return_text=True,
    )

    assert response is not None, response
    assert isinstance(response, dict), response
    assert "content" in response, response
    assert datetime.now().strftime("%Y-%m-%d") in response["content"], response[
        "content"
    ]


def test_analyze_image(integration: OpenAIResponsesIntegration):
    image_url = "https://upload.wikimedia.org/wikipedia/commons/thumb/d/dd/Gfp-wisconsin-madison-the-nature-boardwalk.jpg/2560px-Gfp-wisconsin-madison-the-nature-boardwalk.jpg"
    response = integration.analyze_image(image_urls=[image_url], return_text=True)

    assert response is not None, response
    assert isinstance(response, dict), response
    assert "content" in response, response
    assert "boardwalk" in response["content"].lower(), response["content"]
    assert "landscape" in response["content"].lower(), response["content"]


def test_analyze_pdf(integration: OpenAIResponsesIntegration):
    pdf_url = "https://assets.group.accor.com/yrj0orc8tx24/NHhsrTDX0ecCjky5bsvSV/6b631aa9885bf8c3ed84fb323a91e310/ACCOR_IMPACT_REPORT_2023.pdf"
    response = integration.analyze_pdf(pdf_url=pdf_url, return_text=True)

    assert response is not None, response
    assert isinstance(response, dict), response
    assert "content" in response, response
    assert "accor" in response["content"].lower(), response["content"]
    assert "2023" in response["content"], response["content"]
    assert "impact report" in response["content"].lower(), response["content"]
