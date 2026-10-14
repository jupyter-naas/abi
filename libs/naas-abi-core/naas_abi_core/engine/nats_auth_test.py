from datetime import UTC, datetime, timedelta

import jwt
import pytest
from naas_abi_core.engine.nats_auth import (
    InvalidServiceTokenError,
    issue_module_token,
    issue_service_token,
    module_key,
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


# Module keys: a module signs for its own identity only.


def test_a_module_token_asserts_the_identity_of_its_key():
    token = issue_module_token("acme.research", module_key(SECRET, "acme.research"))

    assert verify_service_token(token, SECRET) == "acme.research"


def test_a_module_key_cannot_sign_another_identity():
    key = module_key(SECRET, "acme.research")
    token = issue_module_token("acme.billing", key)

    with pytest.raises(InvalidServiceTokenError):
        verify_service_token(token, SECRET)


@pytest.mark.parametrize("identity", ["api", "engine", "dagster"])
def test_no_module_key_exists_for_a_first_party_identity(identity):
    with pytest.raises(ValueError, match="first-party"):
        module_key(SECRET, identity)


@pytest.mark.parametrize("identity", ["api", "engine", "dagster"])
def test_a_module_token_never_asserts_a_first_party_identity(identity):
    """Even signed with the right derivation, a module token is not first-party."""
    import base64
    import hashlib
    import hmac

    key = base64.urlsafe_b64encode(
        hmac.new(SECRET.encode(), f"abi.module-key.v1:{identity}".encode(), hashlib.sha256).digest()
    ).rstrip(b"=").decode()
    token = jwt.encode({"sub": identity, "exp": 4102444800}, key, algorithm="HS256", headers={"kid": "module"})

    with pytest.raises(InvalidServiceTokenError, match="first-party"):
        verify_service_token(token, SECRET)


def test_a_module_key_is_not_the_project_secret():
    """A module token signed with the secret itself is refused: only keys sign them."""
    token = jwt.encode(
        {"sub": "acme.research", "exp": 4102444800}, SECRET, algorithm="HS256", headers={"kid": "module"}
    )

    with pytest.raises(InvalidServiceTokenError):
        verify_service_token(token, SECRET)


def test_a_module_key_does_not_sign_first_party_tokens():
    """Without the module header, the token is checked against the project secret."""
    token = issue_service_token("api", module_key(SECRET, "acme.research"))

    with pytest.raises(InvalidServiceTokenError):
        verify_service_token(token, SECRET)


def test_module_keys_differ_per_identity_and_per_secret():
    assert module_key(SECRET, "a") != module_key(SECRET, "b")
    assert module_key(SECRET, "a") != module_key("another-secret", "a")
    assert module_key(SECRET, "a") == module_key(SECRET, "a")
