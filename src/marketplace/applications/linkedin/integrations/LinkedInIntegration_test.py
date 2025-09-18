import pytest

import pydash as _
from src.marketplace.applications.linkedin.integrations.LinkedInIntegration import (
    LinkedInIntegration, 
    LinkedInIntegrationConfiguration
)

DEFAULT_COMPANY_URL = 'https://www.linkedin.com/company/naas-ai/'
DEFAULT_PROFILE_URL = 'https://www.linkedin.com/in/florent-ravenel/'
DEFAULT_PROFILE_ID = "ACoAABCNSioBW3YZHc2lBHVG0E_TXYWitQkmwog"
DEFAULT_POST_URL = 'https://www.linkedin.com/posts/jeremyravenel_do-you-know-that-one-of-the-most-impactful-activity-7244092056774610944-_5eh?utm_source=share&utm_medium=member_desktop&rcm=ACoAABCNSioBW3YZHc2lBHVG0E_TXYWitQkmwog'
DEFAULT_MUTUAL_CONNECTIONS_PROFILE_ID = "ACoAAAJHE7sB5OxuKHuzguZ9L6lfDHqw--cdnJg"

@pytest.fixture
def integration() -> LinkedInIntegration:
    from src import secret
    li_at: str = secret.get('li_at')
    JSESSIONID: str = secret.get('JSESSIONID')
    configuration = LinkedInIntegrationConfiguration(li_at=li_at, JSESSIONID=JSESSIONID)
    return LinkedInIntegration(configuration)

def test_get_organization_info(integration: LinkedInIntegration):
    data = integration.get_organization_info(DEFAULT_COMPANY_URL)

    assert data is not None, data
    assert data.get('data') is not None, data
    assert data.get('included') is not None, data

def test_get_profile_view(integration: LinkedInIntegration):
    data = integration.get_profile_view(DEFAULT_PROFILE_URL)

    assert data is not None, data
    assert data.get('data') is not None, data
    assert data.get('included') is not None, data

def test_get_profile_top_card(integration: LinkedInIntegration):
    data = integration.get_profile_top_card(DEFAULT_PROFILE_URL)
    
    assert data is not None, data
    assert data.get('data') is not None, data
    assert data.get('included') is not None, data

def test_get_profile_skills(integration: LinkedInIntegration):
    data = integration.get_profile_skills(DEFAULT_PROFILE_URL)

    assert data is not None, data
    assert data.get('data') is not None, data
    assert data.get('included') is not None, data

def test_get_profile_network_info(integration: LinkedInIntegration):
    data = integration.get_profile_network_info(DEFAULT_PROFILE_URL)

    assert data is not None, data
    assert data.get('data') is not None, data
    assert data.get('included') is not None, data

def test_get_profile_posts_feed(integration: LinkedInIntegration):
    data = integration.get_profile_posts_feed(DEFAULT_PROFILE_ID, count=1)

    assert data is not None, data
    assert data.get('data') is not None, data
    assert data.get('included') is not None, data

def test_get_post_stats(integration: LinkedInIntegration):
    data = integration.get_post_stats(DEFAULT_POST_URL)

    assert data is not None, data
    assert data.get('data') is not None, data
    assert data.get('included') is not None, data

def test_get_post_comments(integration: LinkedInIntegration):
    data = integration.get_post_comments(DEFAULT_POST_URL)

    assert data is not None, data
    assert data.get('data') is not None, data
    assert data.get('included') is not None, data

def test_get_post_reactions(integration: LinkedInIntegration):
    data = integration.get_post_reactions(DEFAULT_POST_URL)

    assert data is not None, data
    assert data.get('data') is not None, data
    assert data.get('included') is not None, data

def test_get_organization_info_cleaned(integration: LinkedInIntegration):
    data = integration.get_organization_info(DEFAULT_COMPANY_URL, return_cleaned_json=True)

    assert data is not None, data

def test_get_profile_view_cleaned(integration: LinkedInIntegration):
    data = integration.get_profile_view(DEFAULT_PROFILE_URL, return_cleaned_json=True)

    assert data is not None, data

def test_get_profile_top_card_cleaned(integration: LinkedInIntegration):
    data = integration.get_profile_top_card(DEFAULT_PROFILE_URL, return_cleaned_json=True)

    assert data is not None, data

def test_get_profile_posts_feed_cleaned(integration: LinkedInIntegration):
    data = integration.get_profile_posts_feed(DEFAULT_PROFILE_ID, count=1, return_cleaned_json=True)

    assert data is not None, data

def test_get_profile_public_id(integration: LinkedInIntegration):
    data = integration.get_profile_public_id(DEFAULT_PROFILE_URL)

    assert data is not None, data
    assert data == "florent-ravenel", data

def test_get_profile_id(integration: LinkedInIntegration):
    data = integration.get_profile_id(DEFAULT_PROFILE_URL)

    assert data is not None, data
    assert data == "ACoAABCNSioBW3YZHc2lBHVG0E_TXYWitQkmwog", data

def test_get_mutual_connexions(integration: LinkedInIntegration):
    data = integration.get_mutual_connexions(DEFAULT_MUTUAL_CONNECTIONS_PROFILE_ID)

    assert data is not None, data
    assert data.get('data') is not None, data
    assert data.get('included') is not None, data
    total_results = _.get(data, 'data.data.searchDashClustersByAll.metadata.totalResultCount', 0)
    assert total_results > 0, f"Expected total results to be greater than 0, got {total_results}"

def test_get_mutual_connexions_cleaned(integration: LinkedInIntegration):
    data = integration.get_mutual_connexions(DEFAULT_MUTUAL_CONNECTIONS_PROFILE_ID, return_cleaned_json=True)

    assert data is not None, data