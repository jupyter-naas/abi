"""``nats.secret``: what an operator may grant an SDK module, and the safe defaults."""

import pytest
from naas_abi_core.engine.engine_configuration.EngineConfiguration import (
    NATSConfiguration,
    NATSSecretConfiguration,
)
from pydantic import ValidationError


def test_nothing_is_granted_by_default():
    config = NATSConfiguration(jwt_secret="x" * 32)

    assert config.secret.modules == {}


def test_a_modules_grant_is_the_names_it_reads_and_writes():
    config = NATSSecretConfiguration.model_validate(
        {
            "modules": {
                "partner": {"read": ["PARTNER_TOKEN"], "write": ["PARTNER_STATE"]},
                "reader": {"read": ["A"]},
                "empty": {},
            }
        }
    )

    assert config.modules["partner"].read == ["PARTNER_TOKEN"]
    assert config.modules["partner"].write == ["PARTNER_STATE"]
    assert config.modules["reader"].write == []
    assert config.modules["empty"].read == []


@pytest.mark.parametrize("identity", ["api", "engine", "dagster", ""])
def test_the_engines_own_processes_are_not_modules(identity):
    with pytest.raises(ValidationError, match="SDK module identities"):
        NATSSecretConfiguration.model_validate({"modules": {identity: {}}})


def test_a_misspelt_key_is_refused_instead_of_granting_nothing():
    with pytest.raises(ValidationError):
        NATSSecretConfiguration.model_validate(
            {"modules": {"partner": {"reads": ["A"]}}}
        )
    with pytest.raises(ValidationError):
        NATSSecretConfiguration.model_validate({"module": {}})


@pytest.mark.parametrize("name", ["", "has space", "a/b", "*", "x" * 300])
def test_only_secret_names_can_be_granted(name):
    for access in ("read", "write"):
        with pytest.raises(ValidationError, match="not a secret name"):
            NATSSecretConfiguration.model_validate(
                {"modules": {"partner": {access: [name]}}}
            )
