import pytest
from typing import Optional

from src.marketplace.modules.applications.linkedin.integrations.LinkedInIntegration import (
    LinkedInIntegration, 
    LinkedInIntegrationConfiguration
)

DEFAULT_COMPANY_URL = 'https://www.linkedin.com/company/naas-ai/'
DEFAULT_PROFILE_URL = 'https://www.linkedin.com/in/florent-ravenel/'
DEFAULT_POST_URL = 'https://www.linkedin.com/posts/jeremyravenel_do-you-know-that-one-of-the-most-impactful-activity-7244092056774610944-_5eh?utm_source=share&utm_medium=member_desktop&rcm=ACoAABCNSioBW3YZHc2lBHVG0E_TXYWitQkmwog'

@pytest.fixture
def integration() -> LinkedInIntegration:
    from src import secret
    from src.marketplace.modules.applications.naas.integrations.NaasIntegration import (
        NaasIntegration, 
        NaasIntegrationConfiguration
    )
    naas_api_key = secret.get('NAAS_API_KEY')
    li_at: Optional[str] = None
    JSESSIONID: Optional[str] = None
    
    if naas_api_key:
        naas_integration_config = NaasIntegrationConfiguration(api_key=naas_api_key)
        li_at_response = NaasIntegration(naas_integration_config).get_secret('li_at')
        li_at = li_at_response.get('secret', {}).get('value') if li_at_response else None
        jsessionid_response = NaasIntegration(naas_integration_config).get_secret('JSESSIONID')
        JSESSIONID = jsessionid_response.get('secret', {}).get('value') if jsessionid_response else None

    if li_at is None or JSESSIONID is None:
        pytest.skip("LinkedIn credentials not available")

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