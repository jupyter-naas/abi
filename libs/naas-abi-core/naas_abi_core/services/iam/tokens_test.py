from datetime import UTC, datetime, timedelta

import jwt
import pytest

from naas_abi_core.engine.nats_auth import InvalidServiceTokenError, JWKSVerifier
from naas_abi_core.services.iam.adapters.secondary.IAMSecretsMemory import (
    IAMSecretsMemory,
)
from naas_abi_core.services.iam.adapters.secondary.IAMStoreMemory import (
    IAMStoreMemory,
)
from naas_abi_core.services.iam.tokens import (
    PUBLISH_AHEAD,
    RETIRE_AFTER,
    VERIFY_RETIRED_FOR,
    TokenIssuer,
)

START = datetime(2026, 10, 15, 12, tzinfo=UTC)


class Clock:
    def __init__(self) -> None:
        self.now = START

    def __call__(self) -> datetime:
        return self.now


@pytest.fixture
def clock() -> Clock:
    return Clock()


@pytest.fixture
def issuer(clock) -> TokenIssuer:
    return TokenIssuer(IAMStoreMemory(), IAMSecretsMemory(), clock=clock)


def kid(token: str) -> str:
    return jwt.get_unverified_header(token)["kid"]


def test_issuer_names_the_install(issuer):
    jwks = issuer.jwks()
    assert jwks["issuer"].startswith("urn:abi:engine:")
    assert [k["kid"] for k in jwks["keys"]]


def test_tokens_verify_against_the_jwks_and_live_ten_minutes(issuer, clock):
    clock.now = datetime.now(UTC)
    issued = issuer.issue(
        "sa_x", kind="service_account", audience="abi:nats", name="engine"
    )
    claims = JWKSVerifier(issuer.jwks).verify(issued.token)
    assert claims.subject == "sa_x" and claims.name == "engine"
    assert claims.lifetime == 600
    assert issued.expires_at == claims.expires_at


def test_ttl_is_capped(issuer):
    with pytest.raises(ValueError):
        TokenIssuer(IAMStoreMemory(), IAMSecretsMemory(), access_ttl_seconds=601)
    issued = issuer.issue(
        "sa_x", kind="service_account", audience="abi:nats", ttl_seconds=5000
    )
    claims = jwt.decode(issued.token, options={"verify_signature": False})
    assert claims["exp"] - claims["iat"] == 600


def test_private_keys_live_in_the_secrets_not_the_store(clock):
    store, secrets = IAMStoreMemory(), IAMSecretsMemory()
    issuer = TokenIssuer(store, secrets, clock=clock)
    token = issuer.issue("sa_x", kind="service_account", audience="abi:nats").token
    record = store.list_signing_keys()[0]
    assert "d" not in record.public_jwk
    assert secrets.get(f"iam/signing-keys/{record.kid}")
    # Another process of the same deployment signs with the same key.
    again = TokenIssuer(store, secrets, clock=clock)
    assert kid(
        again.issue("sa_x", kind="service_account", audience="abi:nats").token
    ) == kid(token)


def test_a_lost_private_key_is_replaced_at_once(clock):
    store, secrets = IAMStoreMemory(), IAMSecretsMemory()
    first = kid(
        TokenIssuer(store, secrets, clock=clock)
        .issue("s", kind="user", audience="a")
        .token
    )
    secrets.delete(f"iam/signing-keys/{first}")
    second = kid(
        TokenIssuer(store, secrets, clock=clock)
        .issue("s", kind="user", audience="a")
        .token
    )
    assert second != first


def test_rotation_publishes_ahead_and_retires_after(issuer, clock):
    first = kid(issuer.issue("s", kind="user", audience="a").token)
    clock.now = START + timedelta(days=30) - PUBLISH_AHEAD
    # Due: the next key is published, the current one still signs.
    assert kid(issuer.issue("s", kind="user", audience="a").token) == first
    published = [k["kid"] for k in issuer.jwks()["keys"]]
    assert len(published) == 2 and published[0] == first
    nxt = published[1]
    clock.now = START + timedelta(days=30)
    assert kid(issuer.issue("s", kind="user", audience="a").token) == nxt
    # The old key stays published for the calls it signed (stored triggers),
    # marked retired, then goes.
    clock.now = START + timedelta(days=30) + RETIRE_AFTER - timedelta(seconds=1)
    assert first in [k["kid"] for k in issuer.jwks()["keys"]]
    clock.now = START + timedelta(days=30) + RETIRE_AFTER
    keys = {k["kid"]: k for k in issuer.jwks()["keys"]}
    assert set(keys) == {first, nxt}
    assert keys[first]["abi_retired_at"] == int(
        (START + timedelta(days=30) + RETIRE_AFTER).timestamp()
    )
    assert "abi_retired_at" not in keys[nxt]
    clock.now = START + timedelta(days=30) + RETIRE_AFTER + VERIFY_RETIRED_FOR
    assert [k["kid"] for k in issuer.jwks()["keys"]] == [nxt]


def test_a_key_that_left_the_jwks_no_longer_verifies(issuer, clock):
    token = issuer.issue("s", kind="user", audience="abi:nats").token
    clock.now = START + timedelta(days=31)
    issuer.issue("s", kind="user", audience="abi:nats")
    clock.now = START + timedelta(days=32)
    with pytest.raises(InvalidServiceTokenError):
        JWKSVerifier(issuer.jwks).verify(token)


def test_a_call_stored_before_a_rotation_still_verifies_after_it():
    """A job trigger waits in its stream for days, then is checked as of the
    time it was stored: its signing key is retired by then."""
    clock = Clock()
    clock.now = datetime.now(UTC)
    start = clock.now
    store, secrets = IAMStoreMemory(), IAMSecretsMemory()
    issuer = TokenIssuer(store, secrets, clock=clock)
    token = issuer.issue("s", kind="user", audience="abi:nats").token
    stored = clock.now.timestamp()
    first = kid(token)
    # The key rotates (day 30), and has been retired for three days.
    clock.now = start + timedelta(days=29, hours=23, minutes=50)
    issuer.issue("s", kind="user", audience="abi:nats")  # publishes the next
    clock.now = start + timedelta(days=30, minutes=1)
    issuer.issue("s", kind="user", audience="abi:nats")  # the next signs
    clock.now = start + timedelta(days=33)
    issuer.issue("s", kind="user", audience="abi:nats")  # retires the first
    verifier = JWKSVerifier(issuer.jwks, clock=lambda: clock.now.timestamp())
    assert verifier.verify(token, at=stored).subject == "s"
    # Never as a token presented now, nor as of a later time.
    with pytest.raises(InvalidServiceTokenError, match="retired"):
        verifier.verify(token)
    with pytest.raises(InvalidServiceTokenError, match="retired"):
        verifier.verify(token, at=(start + timedelta(days=31)).timestamp())
    # Its private half is gone: nothing signs with it again, or can be forged.
    assert secrets.get(f"iam/signing-keys/{first}") is None
    # And after the longest a call waits, it leaves the JWKS.
    clock.now = start + timedelta(days=30, minutes=30) + VERIFY_RETIRED_FOR
    issuer.issue("s", kind="user", audience="abi:nats")
    assert first not in [k["kid"] for k in issuer.jwks()["keys"]]
