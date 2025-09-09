import pytest

@pytest.fixture
def agent():
    from src.core.modules.perplexity.agents.PerplexityAgent import create_agent
    return create_agent()

def test_agent_name(agent):
    result = agent.invoke("What is your name?")

    assert result is not None, result
    assert "Perplexity" in result, result

def test_search_news_with_datetime(agent):
    from datetime import datetime

    result = agent.invoke("What are the news of the day? Start by: 'As of today the date is YYYY-MM-DD.'")

    assert result is not None, result
    assert datetime.now().strftime("%Y-%m-%d") in result, result
    assert "sources" in result.lower(), result