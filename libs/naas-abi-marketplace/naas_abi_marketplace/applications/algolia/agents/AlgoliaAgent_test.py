import pytest
from naas_abi_marketplace.applications.algolia.agents.AlgoliaAgent import create_agent


@pytest.fixture
def agent():
    return create_agent()


def test_agent(agent):
    response = agent.run("Search in Algolia index")
    assert response is not None
    assert "search" in response.lower()
