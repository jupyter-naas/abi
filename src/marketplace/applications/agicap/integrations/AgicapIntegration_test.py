import pytest

from src.marketplace.applications.agicap.integrations.AgicapIntegration import (
    AgicapIntegration,
    AgicapIntegrationConfiguration,
)

@pytest.fixture
def integration() -> AgicapIntegration:
    from src import secret

    configuration = AgicapIntegrationConfiguration(
        username=secret.get("AGICAP_USERNAME"),
        password=secret.get("AGICAP_PASSWORD"),
        client_id=secret.get("AGICAP_CLIENT_ID"),
        client_secret=secret.get("AGICAP_CLIENT_SECRET"),
        api_token=secret.get("AGICAP_API_TOKEN"),
    )
    return AgicapIntegration(configuration)

def test_list_companies(integration: AgicapIntegration):
    """Test listing companies."""
    companies = integration.list_companies()
    assert companies is not None
    assert len(companies) > 0

def test_get_company_accounts(integration: AgicapIntegration):
    """Test getting company accounts."""
    companies = integration.list_companies()
    assert companies is not None
    assert len(companies) > 0
    company_id = companies[0].get("id")
    accounts = integration.get_company_accounts(company_id=company_id)
    assert accounts is not None
    assert len(accounts) > 0