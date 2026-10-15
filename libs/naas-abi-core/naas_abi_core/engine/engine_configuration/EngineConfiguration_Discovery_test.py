import pytest
from naas_abi_core.engine.engine_configuration.EngineConfiguration import (
    NATSConfiguration,
)
from pydantic import ValidationError


def test_discovery_is_opt_in_and_has_bounded_defaults():
    assert NATSConfiguration().discovery is None
    config = NATSConfiguration(discovery={})
    assert config.discovery.project == "default"
    assert config.discovery.lease_seconds == 20


@pytest.mark.parametrize(
    "discovery",
    [{"project": "a.*"}, {"lease_seconds": 0}, {"lease_seconds": float("inf")}],
)
def test_invalid_discovery_configuration_is_rejected(discovery):
    with pytest.raises(ValidationError):
        NATSConfiguration(discovery=discovery)


def test_monitoring_url_is_optional_and_must_be_http():
    assert NATSConfiguration().monitoring_url is None
    config = NATSConfiguration(monitoring_url="http://nats:8222")
    assert config.monitoring_url == "http://nats:8222"
    with pytest.raises(ValidationError):
        NATSConfiguration(monitoring_url="nats://nats:4222")
