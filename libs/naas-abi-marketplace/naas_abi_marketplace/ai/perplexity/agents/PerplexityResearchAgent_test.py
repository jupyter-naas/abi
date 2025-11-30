import pytest


@pytest.fixture
def agent():
    from naas_abi.core.perplexity.agents.PerplexityAgent import create_agent

    return create_agent()


def test_agent_name(agent):
    result = agent.invoke("What is your name?")

    assert result is not None, result
    assert "Perplexity" in result, result


def test_search_news_with_datetime(agent):
    from datetime import datetime

    result = agent.invoke(
        "What are the news of the day? Start by: 'As of today the date is YYYY-MM-DD.'"
    )

    assert result is not None, result
    assert datetime.now().strftime("%Y-%m-%d") in result, result
    assert "sources" in result.lower(), result


def test_search_news_intent(agent):
    result = agent.invoke("search news about artificial intelligence")

    assert result is not None, result
    assert "artificial intelligence" in result.lower(), result
    assert "sources" in result.lower(), result


def test_search_web_intent(agent):
    result = agent.invoke("search web about climate change")

    assert result is not None, result
    assert "climate change" in result.lower(), result
    assert "sources" in result.lower(), result


def test_research_online_intent(agent):
    result = agent.invoke("research online about quantum computing")

    assert result is not None, result
    assert "quantum computing" in result.lower(), result
    assert "sources" in result.lower(), result


def test_latest_events_intent(agent):
    result = agent.invoke("latest events about space exploration")

    assert result is not None, result
    assert "space exploration" in result.lower(), result
    assert "sources" in result.lower(), result
