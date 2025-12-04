import pytest
from naas_abi_marketplace.applications.google_search.agents.GoogleSearchAgent import (
    create_agent as create_google_search_agent,
)


@pytest.fixture
def agent():
    return create_google_search_agent()


def test_search_web_intent(agent):
    """Test that search web intent triggers googlesearch_query tool."""
    result = agent.invoke("Search the web for Python programming")

    assert result is not None, result
    assert "python" in result.lower() or "programming" in result.lower(), result


def test_search_linkedin_profile_intent(agent):
    """Test that search LinkedIn profile intent triggers googlesearch_search_linkedin_profile_page tool."""
    person_name = "florent ravenel"
    result = agent.invoke(f"Search for a LinkedIn profile: {person_name}")

    assert result is not None, result
    assert "/in/" in result.lower() or "linkedin" in result.lower(), result


def test_search_linkedin_organization_intent(agent):
    """Test that search LinkedIn organization intent triggers googlesearch_search_linkedin_organization_page tool."""
    organization_name = "naas ai"
    result = agent.invoke(f"Search for a LinkedIn organization: {organization_name}")

    assert result is not None, result
    assert "/company/" in result.lower() or "linkedin" in result.lower(), result


def test_find_linkedin_profile_intent(agent):
    """Test alternative intent phrasing for finding LinkedIn profile."""
    person_name = "florent ravenel"
    result = agent.invoke(f"Find LinkedIn profile for {person_name}")

    assert result is not None, result
    assert "/in/" in result.lower() or "linkedin" in result.lower(), result


def test_find_linkedin_company_intent(agent):
    """Test alternative intent phrasing for finding LinkedIn company."""
    organization_name = "naas ai"
    result = agent.invoke(f"Find LinkedIn company: {organization_name}")

    assert result is not None, result
    assert "/company/" in result.lower() or "linkedin" in result.lower(), result
