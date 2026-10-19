import time
from typing import Any

import jwt
import pytest
from naas_abi_core.engine.nats_auth import (
    MAX_TOKEN_SECONDS,
    InvalidServiceTokenError,
    IssuedToken,
    JWKSVerifier,
    RenewingTokenSource,
    SigningKey,
    TokenClaims,
    is_delegated_audience,
    parse_key,
    sign_token,
)

ISSUER = "urn:abi:engine:test"


def claims(**overrides) -> TokenClaims:
    now = int(time.time())
    values: dict[str, Any] = {
        "issuer": ISSUER,
        "subject": "sa_01jabcdefghjkmnpqrstvwxyz0",
        "audience": "abi:nats",
        "kind": "service_account",
        "token_id": "t1",
        "issued_at": now,
        "expires_at": now + 600,
        "name": "module/acme/people",
    }
    values.update(overrides)
    return TokenClaims(**values)


@pytest.fixture
def key() -> SigningKey:
    return SigningKey.generate()


def verifier_for(*keys: SigningKey, **options) -> JWKSVerifier:
    return JWKSVerifier(
        lambda: {"issuer": ISSUER, "keys": [k.public_jwk() for k in keys]}, **options
    )


def test_round_trip_keeps_every_claim(key):
    original = claims(
        actor="sa_01jabcdefghjkmnpqrstvwxyz1",
        actor_name="module/acme/people",
        groups=("grp_01jabcdefghjkmnpqrstvwxyz0",),
        scope=({"effect": "Allow", "actions": ["a:B"], "resources": ["*"]},),
        session="s1",
        since=1_700_000_000,
        resource="abi:-:-:discovery:module/p/acme.people",
    )
    verified = verifier_for(key).verify(sign_token(key, original))
    assert verified == original


def test_tokens_name_their_key(key):
    header = jwt.get_unverified_header(sign_token(key, claims()))
    assert header == {"alg": "ES256", "kid": key.kid, "typ": "JWT"}
    assert key.kid[8] == "-" and len(key.kid) == 17


def test_issuer_refuses_tokens_longer_than_ten_minutes(key):
    now = int(time.time())
    with pytest.raises(ValueError, match="600"):
        sign_token(key, claims(issued_at=now, expires_at=now + MAX_TOKEN_SECONDS + 1))


def test_verifier_refuses_tokens_longer_than_ten_minutes(key):
    now = int(time.time())
    payload = claims(issued_at=now, expires_at=now + 3600).to_payload()
    token = jwt.encode(
        payload, key.private_key, algorithm="ES256", headers={"kid": key.kid}
    )
    with pytest.raises(InvalidServiceTokenError, match="ten minutes"):
        verifier_for(key).verify(token)


def test_verifier_refuses_another_key(key):
    other = SigningKey.generate()
    with pytest.raises(InvalidServiceTokenError):
        verifier_for(key).verify(sign_token(other, claims()))


def test_verifier_refuses_a_forged_kid(key):
    other = SigningKey.generate()
    forged = SigningKey(key.kid, other.private_key)
    with pytest.raises(InvalidServiceTokenError):
        verifier_for(key).verify(sign_token(forged, claims()))


def test_verifier_refuses_hs256_even_with_the_public_key_as_secret(key):
    token = jwt.encode(
        claims().to_payload(),
        "a-shared-secret-of-at-least-32-bytes!",
        algorithm="HS256",
        headers={"kid": key.kid},
    )
    with pytest.raises(InvalidServiceTokenError, match="ES256"):
        verifier_for(key).verify(token)


def test_verifier_refuses_another_issuer(key):
    with pytest.raises(InvalidServiceTokenError):
        verifier_for(key).verify(sign_token(key, claims(issuer="urn:abi:engine:x")))


def test_verifier_refuses_an_audience_it_does_not_accept(key):
    token = sign_token(key, claims(audience="abi:session"))
    with pytest.raises(InvalidServiceTokenError, match="audience"):
        verifier_for(key).verify(token)
    assert verifier_for(key, audiences=("abi:session",)).verify(token).audience


def test_verifier_refuses_expired_tokens_after_the_skew(key):
    now = int(time.time())
    token = sign_token(key, claims(issued_at=now - 700, expires_at=now - 100))
    with pytest.raises(InvalidServiceTokenError):
        verifier_for(key).verify(token)
    recent = sign_token(key, claims(issued_at=now - 610, expires_at=now - 10))
    assert verifier_for(key).verify(recent)  # within 30 s of skew


def test_verifier_refuses_malformed_tokens(key):
    for token in ("", "not-a-jwt", "a.b.c"):
        with pytest.raises(InvalidServiceTokenError):
            verifier_for(key).verify(token)


def test_unknown_kid_refetches_at_most_every_30_seconds(key):
    later = SigningKey.generate()
    published = [key]
    fetches = []
    now = [1000.0]

    def fetch():
        fetches.append(now[0])
        return {"issuer": ISSUER, "keys": [k.public_jwk() for k in published]}

    verifier = JWKSVerifier(fetch, clock=lambda: now[0])
    stamp = int(time.time())
    token = sign_token(later, claims(issued_at=stamp, expires_at=stamp + 600))
    with pytest.raises(InvalidServiceTokenError):
        verifier.verify(token)
    published.append(later)
    now[0] += 10
    with pytest.raises(InvalidServiceTokenError):
        verifier.verify(token)  # still within 30 s: no refetch
    now[0] += 25
    assert verifier.verify(token).subject
    assert fetches == [1000.0, 1035.0]


def test_jwks_is_cached_for_five_minutes(key):
    fetches = []
    now = [0.0]

    def fetch():
        fetches.append(now[0])
        return {"issuer": ISSUER, "keys": [key.public_jwk()]}

    verifier = JWKSVerifier(fetch, clock=lambda: now[0])
    token = sign_token(key, claims())
    verifier.verify(token)
    now[0] = 299
    verifier.verify(token)
    now[0] = 300
    verifier.verify(token)
    assert fetches == [0.0, 300]


def test_an_unreachable_jwks_backs_off_and_keeps_known_keys_a_while(key):
    fetches = []
    now = [0.0]
    up = [True]

    def fetch():
        fetches.append(now[0])
        if not up[0]:
            raise TimeoutError("engine unreachable")
        return {"issuer": ISSUER, "keys": [key.public_jwk()]}

    verifier = JWKSVerifier(fetch, clock=lambda: now[0])
    token = sign_token(key, claims())
    verifier.verify(token)
    up[0] = False
    now[0] = 300  # the cache expired: one attempt fails, the known keys verify
    assert verifier.verify(token).subject
    now[0] = 302  # backing off: no attempt
    assert verifier.verify(token).subject
    now[0] = 306
    assert verifier.verify(token).subject
    assert fetches == [0.0, 300, 306]
    now[0] = 1200  # 15 minutes past the cache: the stale keys stop verifying
    with pytest.raises(InvalidServiceTokenError, match="cannot read the JWKS"):
        verifier.verify(token)
    up[0] = True
    now[0] = 1206
    assert verifier.verify(token).subject


def test_a_slow_fetch_does_not_hold_up_verifiers_with_keys(key):
    import threading

    release = threading.Event()
    fetching = threading.Event()
    now = [0.0]
    calls = []

    def fetch():
        calls.append(now[0])
        if len(calls) > 1:
            fetching.set()
            release.wait(5)
        return {"issuer": ISSUER, "keys": [key.public_jwk()]}

    verifier = JWKSVerifier(fetch, clock=lambda: now[0])
    token = sign_token(key, claims())
    verifier.verify(token)
    now[0] = 300
    slow = threading.Thread(target=verifier.verify, args=(token,))
    slow.start()
    assert fetching.wait(5)
    started = time.monotonic()
    assert verifier.verify(token).subject  # the stale keys, at once
    assert time.monotonic() - started < 1
    release.set()
    slow.join(5)
    assert len(calls) == 2


def test_pem_round_trip(key):
    restored = SigningKey.from_pem(key.kid, key.private_pem())
    assert restored.public_jwk() == key.public_jwk()


def test_claims_refuse_unknown_kinds_and_several_audiences(key):
    payload = claims().to_payload()
    with pytest.raises(InvalidServiceTokenError):
        TokenClaims.from_payload({**payload, "kind": "admin"})
    with pytest.raises(InvalidServiceTokenError):
        TokenClaims.from_payload({**payload, "aud": ["abi:nats", "abi:session"]})


def test_renewing_source_renews_at_half_life():
    now = [0.0]
    issued = []

    def fetch():
        issued.append(now[0])
        return IssuedToken(f"t{len(issued)}", now[0] + 600)

    source = RenewingTokenSource("engine", fetch, clock=lambda: now[0])
    assert source.token() == "t1"
    now[0] = 299
    assert source.token() == "t1"
    now[0] = 300
    assert source.token() == "t2"
    source.invalidate()
    assert source.token() == "t3"


def test_renewing_source_keeps_a_valid_token_when_renewal_fails():
    now = [0.0]
    calls = []

    def fetch():
        calls.append(now[0])
        if len(calls) > 1:
            raise ConnectionError("engine away")
        return IssuedToken("t1", 600)

    source = RenewingTokenSource("engine", fetch, clock=lambda: now[0])
    source.token()
    now[0] = 400
    assert source.token() == "t1"
    now[0] = 599
    with pytest.raises(ConnectionError):
        source.token()


def test_parse_key():
    assert parse_key("abi_sk_abcdefghijklmnop_c2VjcmV0_-x") == (
        "abi_sk_",
        "abcdefghijklmnop",
        "c2VjcmV0_-x",
    )
    assert parse_key("abi_pk_abcdefghijklmnop_c2VjcmV0")[0] == "abi_pk_"
    assert parse_key("abi_gk_abcdefghijklmnop_c2VjcmV0")[0] == "abi_gk_"
    for bad in (
        "",
        "abi_sk_short_x",
        "abi_xx_abcdefghijklmnop_x",
        "abi_sk_ABCDEFGHIJKLMNOP_x",
    ):
        with pytest.raises(ValueError):
            parse_key(bad)


def test_delegated_audiences_are_a_closed_family():
    from naas_abi_core.engine import nats_auth

    assert nats_auth.SESSION_AUDIENCE == "abi:session"
    assert set(nats_auth.DELEGATED_AUDIENCES) == {
        "abi:delegated:agent",
        "abi:delegated:app",
        "abi:delegated:preview",
        "abi:delegated:coding",
        "abi:delegated:api-key",
    }
    assert all(is_delegated_audience(a) for a in nats_auth.DELEGATED_AUDIENCES)
    assert not is_delegated_audience("abi:session")
    assert not is_delegated_audience("abi:delegated:other")
    assert not is_delegated_audience("abi:nats")
    # Key exchange never mints them: they come from token exchange only.
    assert not nats_auth.issuable_audience("abi:session")
    assert not any(
        nats_auth.issuable_audience(a) for a in nats_auth.DELEGATED_AUDIENCES
    )
    # Kernel services accept service tokens and agent delegations, nothing else.
    assert nats_auth.KERNEL_AUDIENCES == ("abi:nats", "abi:delegated:agent")


def test_a_revoked_token_is_refused(key):
    token = sign_token(key, claims(audience="abi:nats", token_id="gone"))
    revoked = verifier_for(key, revoked=lambda c: c.token_id == "gone")
    with pytest.raises(InvalidServiceTokenError, match="revoked"):
        revoked.verify(token)
    # The check survives for_audiences: a narrower verifier is no escape.
    with pytest.raises(InvalidServiceTokenError, match="revoked"):
        revoked.for_audiences(("abi:nats",)).verify(token)
    other = sign_token(key, claims(token_id="fine"))
    assert revoked.verify(other).token_id == "fine"


def test_a_stored_call_is_checked_for_revocation_too(key):
    # ``at``: a job trigger is checked as of its stored time, and still asked
    # whether the credential was revoked since.
    token = sign_token(key, claims())
    seen = []
    verifier = verifier_for(key, revoked=lambda c: seen.append(c.issued_at) or False)
    verifier.verify(token, at=time.time())
    assert len(seen) == 1


# -- delegation: a token that carries the user, in place of a header -------------------


def _user(user_id="usr_1", groups=()):
    from naas_abi_core.engine.call_context import Principal

    return Principal(id=user_id, kind="user", groups=frozenset(groups))


def test_a_source_without_a_delegate_calls_as_itself():
    source = RenewingTokenSource(
        "module", lambda: IssuedToken("own", time.time() + 600)
    )
    assert source.token_for(_user()) == "own"
    assert source.token_for(None) == "own"
    assert source.token_for(_user(), "HOST") == "own"


def test_a_delegating_source_carries_the_user_and_renews_at_half_life():
    now = [1000.0]
    issued: list[tuple[str, str | None]] = []

    def delegate(user, recipient, scope=None):
        issued.append((user.id, recipient))
        return IssuedToken(f"t{len(issued)}", now[0] + 600)

    source = RenewingTokenSource(
        "api",
        lambda: IssuedToken("own", now[0] + 600),
        delegate=delegate,
        clock=lambda: now[0],
    )
    assert source.token_for(_user("a")) == "t1"
    assert source.token_for(_user("a")) == "t1"  # cached
    assert source.token_for(_user("b")) == "t2"
    assert source.token_for(None) == "own"  # no user: the source's own token
    assert source.token_for(_user("a"), "HOST") == "t3"  # one per recipient
    assert source.token_for(_user("a", ["grp_1"])) == "t4"  # groups are claims
    now[0] += 301
    assert source.token_for(_user("a")) == "t5"
    assert issued[0] == ("a", None) and issued[2] == ("a", "HOST")


def test_a_delegation_that_cannot_be_made_is_an_error_not_the_sources_own_token():
    def refuse(user, recipient, scope=None):
        raise InvalidServiceTokenError("user is suspended")

    source = RenewingTokenSource(
        "api", lambda: IssuedToken("own", time.time() + 600), delegate=refuse
    )
    with pytest.raises(InvalidServiceTokenError, match="suspended"):
        source.token_for(_user())


def test_a_delegation_failing_to_renew_keeps_the_valid_token():
    now = [1000.0]
    calls = [0]

    def delegate(user, recipient, scope=None):
        calls[0] += 1
        if calls[0] > 1:
            raise ConnectionError("engine restarting")
        return IssuedToken("t1", now[0] + 600)

    source = RenewingTokenSource(
        "engine",
        lambda: IssuedToken("own", now[0] + 600),
        delegate=delegate,
        clock=lambda: now[0],
    )
    assert source.token_for(_user()) == "t1"
    now[0] += 400  # past half, still valid
    assert source.token_for(_user()) == "t1"
    now[0] += 250  # expired
    with pytest.raises(ConnectionError):
        source.token_for(_user())


def test_the_delegation_cache_is_bounded():
    source = RenewingTokenSource(
        "api",
        lambda: IssuedToken("own", time.time() + 600),
        delegate=lambda u, r, s: IssuedToken(u.id, time.time() + 600),
    )
    for index in range(5000):
        source.token_for(_user(f"u{index}"))
    assert len(source._delegations) <= 2048


def test_a_delegation_keeps_the_scope_of_the_credential_the_call_runs_under():
    seen = []

    def delegate(user, recipient, scope=None):
        seen.append(scope)
        return IssuedToken(f"t{len(seen)}", time.time() + 600)

    source = RenewingTokenSource(
        "api", lambda: IssuedToken("own", time.time() + 600), delegate=delegate
    )
    read = ({"effect": "Allow", "actions": ["a:B"], "resources": ["*"]},)
    other = ({"effect": "Allow", "actions": ["a:C"], "resources": ["*"]},)
    assert source.token_for(_user(), None, read) == "t1"
    assert source.token_for(_user(), None, read) == "t1"
    # A narrower credential never shares a token with a wider one.
    assert source.token_for(_user()) == "t2"
    assert source.token_for(_user(), None, other) == "t3"
    assert seen == [read, None, other]
