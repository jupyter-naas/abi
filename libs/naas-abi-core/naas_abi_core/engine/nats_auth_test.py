from datetime import UTC, datetime, timedelta

import pytest
from naas_abi_core.engine.nats_auth import (
    InvalidServiceTokenError,
    issue_service_token,
    verify_service_token,
)

SECRET = "test-shared-secret"


def test_issue_and_verify_round_trips_identity():
    token = issue_service_token("api", SECRET)

    assert verify_service_token(token, SECRET) == "api"


def test_verify_rejects_wrong_secret():
    token = issue_service_token("api", SECRET)

    with pytest.raises(InvalidServiceTokenError):
        verify_service_token(token, "a-different-secret")


def test_verify_rejects_malformed_token():
    with pytest.raises(InvalidServiceTokenError):
        verify_service_token("not-a-jwt", SECRET)


def test_verify_rejects_expired_token():
    issued_at = datetime.now(UTC) - timedelta(hours=2)
    token = issue_service_token(
        "dagster", SECRET, ttl=timedelta(hours=1), now=issued_at
    )

    with pytest.raises(InvalidServiceTokenError):
        verify_service_token(token, SECRET)


def test_issue_rejects_empty_identity():
    with pytest.raises(ValueError, match="identity"):
        issue_service_token("", SECRET)


def test_different_identities_are_distinguishable():
    api_token = issue_service_token("api", SECRET)
    dagster_token = issue_service_token("dagster", SECRET)

    assert verify_service_token(api_token, SECRET) == "api"
    assert verify_service_token(dagster_token, SECRET) == "dagster"
