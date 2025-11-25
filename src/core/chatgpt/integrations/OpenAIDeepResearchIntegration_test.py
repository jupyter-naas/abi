import pytest

from src.core.chatgpt import ABIModule
from src.core.chatgpt.integrations.OpenAIDeepResearchIntegration import (
    DeepResearchModel,
    OpenAIDeepResearchIntegration,
    OpenAIDeepResearchIntegrationConfiguration,
)


@pytest.fixture
def integration() -> OpenAIDeepResearchIntegration:
    module: ABIModule = ABIModule.get_instance()

    configuration = OpenAIDeepResearchIntegrationConfiguration(
        openai_api_key=module.configuration.openai_api_key,
        model=DeepResearchModel.o3_deep_research,
    )
    return OpenAIDeepResearchIntegration(configuration)


def test_deep_research_default_system_prompt(
    integration: OpenAIDeepResearchIntegration,
):
    query = """
I need to find the following information about the company Michelin for the year 2024:
- Revenue
- Net Income
- EBITDA
- Cash Flow
- Debt
- Equity"""
    response = integration.run(query)
    import rich

    rich.inspect(response)
    rich.print(f"Output text: {response.output_text}")
    assert "Michelin" in response.output_text, response.output_text
    assert "Revenue" in response.output_text, response.output_text
    assert "Net Income" in response.output_text, response.output_text
    assert "EBITDA" in response.output_text, response.output_text
    assert "Cash Flow" in response.output_text, response.output_text
    assert "Debt" in response.output_text, response.output_text
    assert "Equity" in response.output_text, response.output_text
