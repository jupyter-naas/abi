import pytest
from naas_abi_core.engine.engine_configuration.EngineConfiguration import (
    NATSConfiguration,
)
from pydantic import ValidationError


def engine(**block):
    return NATSConfiguration(jwt_secret="test-only", engine=block).engine


def test_an_engine_serves_by_default_with_a_twenty_second_lease():
    settings = NATSConfiguration(jwt_secret="test-only").engine

    assert settings.role == "serve"
    assert settings.rollout_id == ""
    assert settings.lease_seconds == 20
    assert settings.standby_timeout_seconds == 900
    # As long as a transfer may stay idle before it expires.
    assert settings.drain_seconds == 60


def test_a_drain_of_zero_closes_sessions_at_once():
    assert engine(drain_seconds=0).drain_seconds == 0


@pytest.mark.parametrize(
    "block",
    [
        {"role": "owner"},
        {"rollout_id": "has space"},
        {"rollout_id": ".starts-with-a-dot"},
        {"rollout_id": "x" * 129},
        {"lease_seconds": 0.5},
        {"lease_seconds": float("inf")},
        {"standby_timeout_seconds": 0},
        {"drain_seconds": -1},
        {"drain_seconds": float("inf")},
        {"unknown": True},
    ],
)
def test_invalid_engine_settings_are_rejected(block):
    with pytest.raises(ValidationError):
        engine(**block)


def test_the_environment_overrides_role_and_rollout():
    settings = engine(role="serve", rollout_id="from-config").resolved(
        {"ABI_ENGINE_ROLE": "client", "ABI_ROLLOUT_ID": "v2.0.1"}
    )

    assert settings.role == "client"
    assert settings.rollout_id == "v2.0.1"


def test_empty_environment_values_keep_the_configuration():
    settings = engine(role="client", rollout_id="from-config").resolved(
        {"ABI_ENGINE_ROLE": "", "ABI_ROLLOUT_ID": ""}
    )

    assert settings.role == "client"
    assert settings.rollout_id == "from-config"


def test_invalid_environment_values_are_rejected():
    with pytest.raises(ValidationError):
        engine().resolved({"ABI_ROLLOUT_ID": "not valid"})
    with pytest.raises(ValidationError):
        engine().resolved({"ABI_ENGINE_ROLE": "standby"})


def test_timing_follows_the_settings():
    timing = engine(lease_seconds=8, standby_timeout_seconds=60).timing()

    assert timing.lease_seconds == 8
    assert timing.standby_timeout_seconds == 60


def test_auto_is_a_role_for_one_off_engines():
    assert engine(role="auto").role == "auto"
    assert engine().resolved({"ABI_ENGINE_ROLE": "auto"}).role == "auto"


def test_a_kernel_service_handles_64_calls_at_once_by_default():
    assert NATSConfiguration(jwt_secret="test-only").max_concurrent_requests == 64


def test_a_kernel_service_handles_at_least_one_call_at_once():
    with pytest.raises(ValidationError):
        NATSConfiguration(jwt_secret="test-only", max_concurrent_requests=0)
