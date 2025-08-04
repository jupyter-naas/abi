import pytest

from src.core.modules.github.agents.GitHubAgent import create_agent

@pytest.fixture
def create_agent():
    return create_agent()

def test_create_bug_report(agent):
    result = agent.invoke("Create a bug report on the topic: Impossible to make chat with agent")

    assert result is not None

def test_create_feature_request(agent):
    result = agent.invoke("Create a feature request on the topic: Add integration with Github to core modules")

    assert result is not None