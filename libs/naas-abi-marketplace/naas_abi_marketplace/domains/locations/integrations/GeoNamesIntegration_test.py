import pytest
from naas_abi_marketplace.domains.locations.integrations.GeoNamesIntegration import (
    GeoNamesIntegration,
    GeoNamesIntegrationConfiguration,
)


@pytest.fixture
def integration(tmp_path) -> GeoNamesIntegration:
    configuration = GeoNamesIntegrationConfiguration(cache_dir=str(tmp_path))
    return GeoNamesIntegration(configuration)


def test_get_country_info(integration: GeoNamesIntegration):
    result = integration.get_country_info()

    assert result is not None
    assert isinstance(result, list)
    assert len(result) > 0

    countries = {r["country_code"]: r["country"] for r in result}
    assert countries["FR"] == "France"


def test_get_postal_codes(integration: GeoNamesIntegration):
    result = integration.get_postal_codes("LU")

    assert result is not None
    assert isinstance(result, list)
    assert len(result) > 0

    record = result[0]
    for field in ["city", "region", "state", "country_code", "postal_code", "latitude", "longitude"]:
        assert field in record
    assert record["country_code"] == "LU"


def test_search_postal_code(integration: GeoNamesIntegration):
    result = integration.search_postal_code("LU", "L-4970")

    assert result is not None
    assert isinstance(result, list)
    assert len(result) > 0
    assert all(r["postal_code"] == "L-4970" for r in result)
