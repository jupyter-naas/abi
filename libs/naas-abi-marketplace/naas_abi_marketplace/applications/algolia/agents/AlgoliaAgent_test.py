import pytest


@pytest.fixture
def agent():
    from naas_abi_core.engine.Engine import Engine
    from naas_abi_marketplace.applications.algolia.agents.AlgoliaAgent import (
        AlgoliaAgent,
    )

    engine = Engine()
    engine.load(module_names=["naas_abi_marketplace.applications.algolia"])

    return AlgoliaAgent.New()


def test_agent(agent):
    response = agent.run("Search in Algolia index")
    assert response is not None
    assert "search" in response.lower()