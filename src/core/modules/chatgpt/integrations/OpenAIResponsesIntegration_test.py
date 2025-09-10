import pytest

from src.core.modules.chatgpt.integrations.OpenAIResponsesIntegration import (
    OpenAIResponsesIntegration, 
    OpenAIResponsesIntegrationConfiguration, 
)

@pytest.fixture
def integration() -> OpenAIResponsesIntegration:
    from src import secret
    
    configuration = OpenAIResponsesIntegrationConfiguration(
        api_key=secret.get('OPENAI_API_KEY'),
    )
    return OpenAIResponsesIntegration(configuration)

def test_web_search(integration: OpenAIResponsesIntegration):
    from datetime import datetime
    
    query = "What's the news today? Start with the date in the format YYYY-MM-DD."
    response = integration.search_web(query=query, search_context_size="medium", return_text=True)

    assert response is not None, response
    assert datetime.now().strftime("%Y-%m-%d") in response, response

def test_analyze_image(integration: OpenAIResponsesIntegration):
    image_url = "https://upload.wikimedia.org/wikipedia/commons/thumb/d/dd/Gfp-wisconsin-madison-the-nature-boardwalk.jpg/2560px-Gfp-wisconsin-madison-the-nature-boardwalk.jpg"
    response = integration.analyze_image(image_url=image_url, return_text=True)
    
    assert response is not None, response
    assert "boardwalk" in response, response
    assert "landscape" in response, response

def test_analyze_pdf(integration: OpenAIResponsesIntegration):
    pdf_url = "https://assets.group.accor.com/yrj0orc8tx24/NHhsrTDX0ecCjky5bsvSV/6b631aa9885bf8c3ed84fb323a91e310/ACCOR_IMPACT_REPORT_2023.pdf"
    response = integration.analyze_pdf(pdf_url=pdf_url, return_text=True)
    
    assert response is not None, response
    assert "accor" in response.lower(), response
    assert "2023" in response, response
    assert "impact report" in response.lower(), response