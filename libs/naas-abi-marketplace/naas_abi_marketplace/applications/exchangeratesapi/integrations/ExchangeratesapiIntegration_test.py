import pytest
from naas_abi_marketplace.applications.exchangeratesapi.integrations.ExchangeratesapiIntegration import (
    ExchangeratesapiIntegration,
    ExchangeratesapiIntegrationConfiguration,
)


@pytest.fixture
def integration() -> ExchangeratesapiIntegration:
    from naas_abi_marketplace.applications.exchangeratesapi import ABIModule

    module = ABIModule.get_instance()
    exchangeratesapi_api_key = module.configuration.exchangeratesapi_api_key

    configuration = ExchangeratesapiIntegrationConfiguration(
        api_key=exchangeratesapi_api_key,
    )
    return ExchangeratesapiIntegration(configuration)


def test_list_symbols(integration: ExchangeratesapiIntegration):
    symbols = integration.list_symbols()

    assert symbols is not None, symbols
    assert symbols.get("success") is True, symbols
    assert len(symbols.get("symbols")) > 0, symbols


def test_get_exchange_rates(integration: ExchangeratesapiIntegration):
    rates = integration.get_exchange_rates(date="2024-12-31", base="EUR", symbols=[])

    assert rates is not None, rates
    assert rates.get("success") is True, rates
    assert rates.get("base") == "EUR", rates
    assert rates.get("date") == "2024-12-31", rates
    assert len(rates.get("rates")) > 0, rates
