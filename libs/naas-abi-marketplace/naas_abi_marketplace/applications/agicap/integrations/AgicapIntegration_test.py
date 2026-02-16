import pytest
from naas_abi_marketplace.applications.agicap.integrations.AgicapIntegration import (
    AgicapIntegration,
    AgicapIntegrationConfiguration,
)


@pytest.fixture
def integration() -> AgicapIntegration:
    from naas_abi_marketplace.applications.agicap import ABIModule

    module = ABIModule.get_instance()
    agicap_username = module.configuration.agicap_username
    agicap_password = module.configuration.agicap_password
    agicap_client_id = module.configuration.agicap_client_id
    agicap_client_secret = module.configuration.agicap_client_secret
    agicap_api_token = module.configuration.agicap_api_token
    agicap_bearer_token = module.configuration.agicap_bearer_token

    configuration = AgicapIntegrationConfiguration(
        username=agicap_username,
        password=agicap_password,
        client_id=agicap_client_id,
        client_secret=agicap_client_secret,
        api_token=agicap_api_token,
        bearer_token=agicap_bearer_token,
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
