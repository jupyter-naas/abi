import pytest

from src.marketplace.applications.aia.integrations.AiaIntegration import (
    AiaIntegration,
    AiaIntegrationConfiguration,
)

@pytest.fixture
def aia_integration() -> AiaIntegration:
    from src import secret

    li_at = secret.get('li_at')
    JSESSIONID = secret.get('JSESSIONID')
    naas_api_key = secret.get('NAAS_API_KEY')
    
    
    aia_integration_config = AiaIntegrationConfiguration(
        api_key=naas_api_key,
        li_at=li_at,
        JSESSIONID=JSESSIONID,
    )
    return AiaIntegration(aia_integration_config)

def test_create_aia(aia_integration: AiaIntegration):
    linkedin_urls = ["https://www.linkedin.com/in/jeremyravenel/"]
    response = aia_integration.create_aia(linkedin_urls)
    assert response is not None, response