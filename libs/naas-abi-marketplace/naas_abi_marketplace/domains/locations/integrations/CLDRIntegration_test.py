import pytest
from naas_abi_marketplace.domains.locations.integrations.CLDRIntegration import (
    CLDRIntegration,
    CLDRIntegrationConfiguration,
)


@pytest.fixture
def integration() -> CLDRIntegration:
    configuration = CLDRIntegrationConfiguration()
    return CLDRIntegration(configuration)


def test_get_territory_name_default_locale(integration: CLDRIntegration):
    assert integration.get_territory_name("FR") == "France"
    assert integration.get_territory_name("US") == "United States"


def test_get_territory_name_other_locale(integration: CLDRIntegration):
    assert integration.get_territory_name("FR", locale="fr") == "France"
    assert integration.get_territory_name("FR", locale="ja") == "フランス"


def test_get_territory_name_unknown_code(integration: CLDRIntegration):
    assert integration.get_territory_name("XX") is None


def test_get_territory_names(integration: CLDRIntegration):
    names = integration.get_territory_names("FR", locales=["en", "fr", "ja"])

    assert names == {"en": "France", "fr": "France", "ja": "フランス"}


def test_get_territories(integration: CLDRIntegration):
    territories = integration.get_territories()

    assert isinstance(territories, list)
    assert len(territories) > 200
    assert {"territory_code": "FR", "name": "France"} in territories


def test_get_language_name(integration: CLDRIntegration):
    assert integration.get_language_name("en") == "English"
    assert integration.get_language_name("en", locale="fr") == "anglais"
