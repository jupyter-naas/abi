import pytest
from naas_abi_marketplace.ai.chatgpt.agents.ChatGPTResearchAgent import (
    ChatGPTResponsesAgent,
)


@pytest.fixture
def agent():
    return ChatGPTResponsesAgent.New()


def test_agent_name(agent):
    result = agent.invoke("what is your name")

    assert result is not None, result
    assert "ChatGPT" in result, result


def test_search_news(agent):
    result = agent.invoke("Which team won the last men's football Champions League?")

    assert result is not None, result
    assert "Paris Saint-Germain" in result, result


def test_search_news_with_datetime(agent):
    from datetime import datetime

    result = agent.invoke(
        "What are the news of the day? Start by: 'As of today the date is YYYY-MM-DD.'"
    )

    assert result is not None, result
    assert datetime.now().strftime("%Y-%m-%d") in result, result
