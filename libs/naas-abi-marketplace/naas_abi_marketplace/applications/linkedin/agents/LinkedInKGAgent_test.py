import pytest
from naas_abi_marketplace.applications.linkedin.agents.LinkedInKGAgent import (
    create_agent as create_linkedin_kg_agent,
)


@pytest.fixture
def agent():
    return create_linkedin_kg_agent()


def test_linkedin_count_connections_by_person(agent):
    assert agent is not None
    question = "How many connections does John Doe have?"
    result = agent.invoke(question)
    assert result is not None
    assert "John Doe" in result
    assert "connections" in result


def test_linkedin_search_connections_by_person(agent):
    question = "Who is connected to John Doe?"
    result = agent.invoke(question)
    assert result is not None
    assert "John Doe" in result


def test_linkedin_search_connections_by_organization(agent):
    question = "Show me connections for people who work at Acme Corp."
    result = agent.invoke(question)
    assert result is not None
    assert "Acme Corp" in result


def test_linkedin_search_connections_by_job_position(agent):
    question = "Which LinkedIn connections are for people who are Software Engineers?"
    result = agent.invoke(question)
    assert result is not None
    assert "Software Engineer" in result or "Software Engineers" in result


def test_linkedin_search_person_info_by_person_uri(agent):
    question = "What is all available LinkedIn information about John Doe?"
    result = agent.invoke(question)
    assert result is not None
    assert "John Doe" in result
