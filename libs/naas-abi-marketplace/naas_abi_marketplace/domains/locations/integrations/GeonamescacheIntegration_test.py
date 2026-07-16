import pytest
from naas_abi_marketplace.domains.locations.integrations.GeonamescacheIntegration import (
    GeonamescacheIntegration,
    GeonamescacheIntegrationConfiguration,
)


@pytest.fixture
def integration() -> GeonamescacheIntegration:
    configuration = GeonamescacheIntegrationConfiguration()
    return GeonamescacheIntegration(configuration)


def test_get_countries(integration: GeonamescacheIntegration):
    result = integration.get_countries()

    assert result is not None
    assert isinstance(result, list)
    assert len(result) > 0
    assert any(c["iso"] == "FR" and c["name"] == "France" for c in result)


def test_get_cities_with_min_population(integration: GeonamescacheIntegration):
    result = integration.get_cities(min_population=10_000_000)

    assert result is not None
    assert isinstance(result, list)
    assert len(result) > 0
    assert all(c["population"] >= 10_000_000 for c in result)


def test_search_cities(integration: GeonamescacheIntegration):
    result = integration.search_cities("Paris")

    assert result is not None
    assert isinstance(result, list)
    assert any(c["name"] == "Paris" and c["countrycode"] == "FR" for c in result)


def test_get_us_states(integration: GeonamescacheIntegration):
    result = integration.get_us_states()

    assert result is not None
    assert isinstance(result, list)
    assert len(result) > 0


def test_get_us_counties(integration: GeonamescacheIntegration):
    result = integration.get_us_counties()

    assert result is not None
    assert isinstance(result, list)
    assert len(result) > 0
