import pytest
from naas_abi_marketplace.applications.newsapi.agents.NewsAPIAgent import create_agent


@pytest.fixture
def agent():
    return create_agent()


def test_agent_name(agent):
    result = agent.invoke("What is your name?")

    assert result is not None, result
    assert "NewsAPI" in result or "News API" in result, result


def test_agent_system_prompt(agent):
    result = agent.invoke("What can you help me with?")

    assert result is not None, result
    assert (
        "news" in result.lower()
        or "article" in result.lower()
        or "headline" in result.lower()
    ), result
