import pytest

from src.core.modules.chatgpt.agents.ChatGPTNativeAgent import create_agent

@pytest.fixture
def agent():
    return create_agent()

def test_agent_name(agent):
    result = agent.invoke("what is your name")

    assert result is not None, result
    assert "ChatGPT" in result, result

def test_search_news(agent):
    result = agent.invoke("Which team won the last men's Champions League?")

    assert result is not None, result
    assert "Paris Saint-Germain" in result, result

def test_search_news_with_datetime(agent):
    from datetime import datetime

    result = agent.invoke("What are the news of the day? Start by: 'As of today the date is YYYY-MM-DD.'")

    assert result is not None, result
    assert datetime.now().strftime("%Y-%m-%d") in result, result

def test_analyze_image(agent):
    image_url = "https://upload.wikimedia.org/wikipedia/commons/thumb/d/dd/Gfp-wisconsin-madison-the-nature-boardwalk.jpg/2560px-Gfp-wisconsin-madison-the-nature-boardwalk.jpg"
    result = agent.invoke(f"Analyze the image: {image_url}")

    assert result is not None, result
    assert "Eiffel Tower" in result, result

def test_analyze_pdf(agent):
    pdf_url = "https://assets.group.accor.com/yrj0orc8tx24/NHhsrTDX0ecCjky5bsvSV/6b631aa9885bf8c3ed84fb323a91e310/ACCOR_IMPACT_REPORT_2023.pdf"
    result = agent.invoke(f"Extract people cited in the PDF: {pdf_url}")

    assert result is not None, result
    assert "Sébastien Bazin" in result, result
    assert 'Brune Poirson' in result, result