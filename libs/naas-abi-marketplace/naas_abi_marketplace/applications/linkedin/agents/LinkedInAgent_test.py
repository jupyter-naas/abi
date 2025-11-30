import pytest
from naas_abi_marketplace.applications.linkedin.agents.LinkedInAgent import (
    create_agent as create_linkedin_agent,
)


@pytest.fixture
def agent():
    return create_linkedin_agent()


def test_search_person_linkedin_url(agent):
    person_name = "florent ravenel"
    result = agent.invoke(f"search {person_name} linkedin URL")

    assert result is not None, result
    assert "/in/florent-ravenel/" in result, result


def test_search_linkedin_organization_url(agent):
    organization_name = "naas ai"
    result = agent.invoke(f"search {organization_name} linkedin URL")

    assert result is not None, result
    assert "/company/naas-ai/" in result, result


def test_get_linkedin_profile_view(agent):
    profile_url = "https://www.linkedin.com/in/florent-ravenel/"
    result = agent.invoke(f"Who is {profile_url}?")

    assert result is not None, result
    assert "florent ravenel" in result.lower(), result


def test_get_linkedin_organization_info(agent):
    organization_url = "https://www.linkedin.com/company/naas-ai/"
    result = agent.invoke(f"What is {organization_url} doing?")

    assert result is not None, result
    assert "naas" in result.lower(), result
