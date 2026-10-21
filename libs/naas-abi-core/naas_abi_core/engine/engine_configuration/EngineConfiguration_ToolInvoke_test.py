"""``nats.tool_registry.invoke``: what an operator may write, and the safe defaults."""

import pytest
from naas_abi_core.engine.engine_configuration.EngineConfiguration import (
    NATSToolInvokeConfiguration,
    NATSToolRegistryConfiguration,
)
from pydantic import ValidationError


def test_nothing_is_granted_by_default():
    config = NATSToolRegistryConfiguration()

    assert config.module_scopes == {}
    assert config.invoke.enabled
    assert config.invoke.modules == {}
    assert (
        config.invoke.max_concurrent,
        config.invoke.default_timeout_seconds,
        config.invoke.max_timeout_seconds,
    ) == (16, 60, 300)


def test_a_modules_grant_is_secret_names_and_tool_patterns():
    config = NATSToolRegistryConfiguration.model_validate(
        {
            "invoke": {
                "modules": {
                    "partner": {
                        "secrets": ["GITHUB_ACCESS_TOKEN"],
                        "unscoped_tools": ["acme.github/get_*"],
                    },
                    "other": {},
                }
            }
        }
    )

    grant = config.invoke.modules["partner"]
    assert grant.secrets == ["GITHUB_ACCESS_TOKEN"]
    assert grant.unscoped_tools == ["acme.github/get_*"]
    assert config.invoke.modules["other"].secrets == []
    assert config.invoke.modules["other"].unscoped_tools == []


@pytest.mark.parametrize("identity", ["api", "engine", "dagster", ""])
def test_the_engines_own_processes_are_not_modules(identity):
    with pytest.raises(ValidationError, match="SDK module identities"):
        NATSToolInvokeConfiguration.model_validate({"modules": {identity: {}}})


@pytest.mark.parametrize("name", ["", "has space", "1LEADING", "a" * 129, "a/b", "*"])
def test_a_secret_is_named_not_matched(name):
    with pytest.raises(ValidationError, match="not a secret name"):
        NATSToolInvokeConfiguration.model_validate(
            {"modules": {"partner": {"secrets": [name]}}}
        )


@pytest.mark.parametrize(
    "field, value",
    [
        ("max_concurrent", 0),
        ("max_concurrent", 257),
        ("default_timeout_seconds", 0),
        ("default_timeout_seconds", 301),
        ("max_timeout_seconds", 301),
        ("max_timeout_seconds", float("inf")),
        ("unknown_field", 1),
    ],
)
def test_limits_stay_within_the_contract(field, value):
    with pytest.raises(ValidationError):
        NATSToolInvokeConfiguration.model_validate({field: value})


@pytest.mark.parametrize(
    "slots, configured, expected",
    [(64, 16, 16), (8, 16, 4), (16, 16, 8), (3, 16, 1), (1, 16, 1), (64, 2, 2)],
)
def test_tool_calls_leave_half_of_the_services_slots_to_the_catalog(
    slots, configured, expected
):
    from naas_abi_core.engine.engine_configuration.EngineConfiguration import (
        NATSConfiguration,
    )

    nats = NATSConfiguration(
        jwt_secret="x" * 32,
        max_concurrent_requests=slots,
        tool_registry={"invoke": {"max_concurrent": configured}},
    )

    assert nats.tool_invoke_concurrency() == expected
