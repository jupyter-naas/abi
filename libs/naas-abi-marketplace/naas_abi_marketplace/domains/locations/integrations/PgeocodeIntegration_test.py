import pytest
from naas_abi_marketplace.domains.locations.integrations.PgeocodeIntegration import (
    PgeocodeIntegration,
    PgeocodeIntegrationConfiguration,
)


@pytest.fixture
def integration() -> PgeocodeIntegration:
    configuration = PgeocodeIntegrationConfiguration()
    return PgeocodeIntegration(configuration)


def test_query_postal_code_single(integration: PgeocodeIntegration):
    result = integration.query_postal_code("FR", "75001")

    assert result is not None
    assert isinstance(result, list)
    assert len(result) == 1

    record = result[0]
    for field in ["city", "region", "state", "country_code", "postal_code", "latitude", "longitude"]:
        assert field in record
    assert record["country_code"] == "FR"
    assert record["postal_code"] == "75001"


def test_query_postal_code_batch(integration: PgeocodeIntegration):
    result = integration.query_postal_code("FR", ["75001", "75002"])

    assert result is not None
    assert isinstance(result, list)
    assert len(result) == 2
    assert {r["postal_code"] for r in result} == {"75001", "75002"}
