import pytest
from naas_abi_core.engine.engine_configuration.EngineConfiguration import (
    NATSConfiguration,
)
from pydantic import ValidationError


def test_discovery_is_opt_in_and_has_bounded_defaults():
    assert NATSConfiguration(jwt_secret="test-only").discovery is None
    config = NATSConfiguration(jwt_secret="test-only", discovery={})
    assert config.discovery.project == "default"
    assert config.discovery.lease_seconds == 20


@pytest.mark.parametrize(
    "discovery",
    [{"project": "a.*"}, {"lease_seconds": 0}, {"lease_seconds": float("inf")}],
)
def test_invalid_discovery_configuration_is_rejected(discovery):
    with pytest.raises(ValidationError):
        NATSConfiguration(jwt_secret="test-only", discovery=discovery)
