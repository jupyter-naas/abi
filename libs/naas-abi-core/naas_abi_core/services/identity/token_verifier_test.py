"""ID token checks and the key cache, on an in-memory provider and clock."""

from __future__ import annotations

import json
from collections.abc import Mapping
from typing import Any

import jwt
import pytest
from cryptography.hazmat.primitives.asymmetric import ec, rsa

from naas_abi_core.services.identity.IdentityPorts import (
    HttpJSON,
    IdentityProvider,
    OIDCHttpPort,
    ProviderUnavailableError,
    TokenRejectedError,
    claim_values,
)
from naas_abi_core.services.identity.provider_keys import ProviderKeys, parse_metadata
from naas_abi_core.services.identity.token_verifier import TokenVerifier

ISSUER = "https://idp.example"
NOW = 1_800_000_000.0


class Clock:
    def __init__(self) -> None:
        self.now = NOW

    def __call__(self) -> float:
        return self.now


class MemoryHttp(OIDCHttpPort):
    def __init__(self) -> None:
        self.keys: list[tuple[str, Any, str]] = []
        self.jwks_reads = 0
        self.down = False
        self.discovery: dict[str, Any] = {
            "issuer": ISSUER,
            "authorization_endpoint": f"{ISSUER}/authorize",
            "token_endpoint": f"{ISSUER}/token",
            "jwks_uri": f"{ISSUER}/jwks",
        }

    def add_key(self, algorithm: str = "RS256") -> tuple[str, Any]:
        private = (
            ec.generate_private_key(ec.SECP256R1())
            if algorithm.startswith("ES")
            else rsa.generate_private_key(public_exponent=65537, key_size=2048)
        )
        kid = f"k{len(self.keys)}"
        self.keys.append((kid, private, algorithm))
        return kid, private

    def get_json(self, url: str) -> HttpJSON:
        if self.down:
            raise ProviderUnavailableError("down")
        if url.endswith("/.well-known/openid-configuration"):
            return HttpJSON(self.discovery)
        self.jwks_reads += 1
        keys = []
        for kid, private, algorithm in self.keys:
            jwk = json.loads(
                jwt.get_algorithm_by_name(algorithm).to_jwk(private.public_key())
            )
            keys.append({**jwk, "kid": kid, "alg": algorithm, "use": "sig"})
        return HttpJSON({"keys": keys})

    def post_form(self, url: str, data: Mapping[str, str], *, basic_auth=None):
        raise AssertionError("no token endpoint here")


@pytest.fixture
def clock() -> Clock:
    return Clock()


@pytest.fixture
def http() -> MemoryHttp:
    return MemoryHttp()


PROVIDER = IdentityProvider(
    name="acme", issuer=ISSUER, client_id="abi", groups_claim="groups"
)


def verifier(http: MemoryHttp, clock: Clock, provider: IdentityProvider = PROVIDER):
    keys = ProviderKeys(
        provider, http, refetch_seconds=30, retry_seconds=5, clock=clock
    )
    return TokenVerifier([keys], clock=clock), keys


def token(http: MemoryHttp, *, kid: str | None = None, algorithm=None, **claims) -> str:
    if not http.keys:
        http.add_key()
    chosen = next((k for k in http.keys if k[0] == kid), http.keys[-1])
    body = {
        "iss": ISSUER,
        "sub": "user-1",
        "aud": "abi",
        "iat": int(NOW),
        "exp": int(NOW) + 300,
        **claims,
    }
    body = {k: v for k, v in body.items() if v is not None}
    return jwt.encode(
        body, chosen[1], algorithm=algorithm or chosen[2], headers={"kid": chosen[0]}
    )


def rejected(fn) -> str:
    with pytest.raises(TokenRejectedError) as refused:
        fn()
    return refused.value.reason


def test_a_valid_token_yields_its_claims(http, clock):
    v, _ = verifier(http, clock)
    verified = v.verify(
        token(
            http, email="a@acme.test", email_verified="true", name="Ada", groups=["x"]
        )
    )
    assert (verified.provider, verified.subject) == ("acme", "user-1")
    assert verified.email == "a@acme.test" and verified.email_verified
    assert verified.display_name == "Ada"
    assert verified.groups == ("x",)


@pytest.mark.parametrize(
    ("claims", "reason"),
    [
        ({"iss": "https://other.example"}, "unknown_issuer"),
        ({"aud": "someone-else"}, "wrong_audience"),
        ({"aud": ["abi", "other"]}, "wrong_audience"),  # several audiences need azp
        ({"azp": "other"}, "wrong_audience"),
        ({"exp": int(NOW) - 31}, "expired"),
        ({"iat": int(NOW) + 31}, "not_yet_valid"),
        ({"nbf": int(NOW) + 31}, "not_yet_valid"),
        ({"sub": None}, "missing_claim"),
        ({"exp": None}, "missing_claim"),
    ],
)
def test_a_token_failing_a_check_is_refused(http, clock, claims, reason):
    v, _ = verifier(http, clock)
    assert rejected(lambda: v.verify(token(http, **claims))) == reason


def test_several_audiences_pass_with_the_client_as_azp(http, clock):
    v, _ = verifier(http, clock)
    assert v.verify(token(http, aud=["abi", "project"], azp="abi")).audience == (
        "abi",
        "project",
    )


def test_clock_skew_is_tolerated(http, clock):
    v, _ = verifier(http, clock)
    assert v.verify(token(http, exp=int(NOW) - 29, iat=int(NOW) + 29)).subject


def test_unsigned_and_hmac_tokens_are_refused(http, clock):
    v, _ = verifier(http, clock)
    http.add_key()
    unsigned = jwt.encode(
        {"iss": ISSUER, "sub": "x", "aud": "abi"}, None, algorithm="none"
    )
    assert rejected(lambda: v.verify(unsigned)) in {"malformed", "algorithm"}
    hmac = jwt.encode(
        {
            "iss": ISSUER,
            "sub": "x",
            "aud": "abi",
            "iat": int(NOW),
            "exp": int(NOW) + 60,
        },
        "a-shared-secret-of-thirty-two-bytes!",
        algorithm="HS256",
        headers={"kid": "k0"},
    )
    assert rejected(lambda: v.verify(hmac)) == "algorithm"


def test_a_token_signed_by_another_key_is_refused(http, clock):
    v, _ = verifier(http, clock)
    http.add_key()
    stranger = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    forged = jwt.encode(
        {
            "iss": ISSUER,
            "sub": "x",
            "aud": "abi",
            "iat": int(NOW),
            "exp": int(NOW) + 60,
        },
        stranger,
        algorithm="RS256",
        headers={"kid": "k0"},
    )
    assert rejected(lambda: v.verify(forged)) == "invalid_signature"


def test_an_algorithm_the_key_does_not_declare_is_refused(http, clock):
    v, _ = verifier(http, clock)
    http.add_key("RS256")
    assert rejected(lambda: v.verify(token(http, algorithm="PS256"))) == "algorithm"


def test_the_provider_must_match_when_named(http, clock):
    v, _ = verifier(http, clock)
    assert rejected(lambda: v.verify(token(http), provider="other")) == "unknown_issuer"


def test_garbage_is_malformed(http, clock):
    v, _ = verifier(http, clock)
    assert rejected(lambda: v.verify("not-a-token")) == "malformed"
    assert rejected(lambda: v.verify("a.b.c")) == "malformed"


# -- the key cache --------------------------------------------------------------


def test_an_unknown_key_refetches_the_jwks_at_most_every_refetch_interval(http, clock):
    v, _ = verifier(http, clock)
    v.verify(token(http))
    assert http.jwks_reads == 1
    new_kid, _ = http.add_key("ES256")
    clock.now += 10
    # Within 30 seconds of the last read the cache is not refetched...
    assert rejected(lambda: v.verify(token(http, kid=new_kid, iat=int(clock.now)))) == (
        "unknown_key"
    )
    assert http.jwks_reads == 1
    clock.now += 21
    # ...then the unknown key is looked up once.
    assert v.verify(
        token(http, kid=new_kid, iat=int(clock.now), exp=int(clock.now) + 60)
    )
    assert http.jwks_reads == 2


def test_known_keys_keep_verifying_while_the_provider_is_down(http, clock):
    v, _ = verifier(http, clock)
    v.verify(token(http))
    http.down = True
    clock.now += 400  # the 300-second cache has expired
    assert v.verify(token(http, iat=int(clock.now), exp=int(clock.now) + 60)).subject
    clock.now += 1000  # past the stale allowance
    with pytest.raises(ProviderUnavailableError):
        v.verify(token(http, iat=int(clock.now), exp=int(clock.now) + 60))


def test_a_discovery_document_for_another_issuer_is_refused(http, clock):
    http.discovery["issuer"] = "https://evil.example"
    v, _ = verifier(http, clock)
    with pytest.raises(ProviderUnavailableError, match="names issuer"):
        v.verify(token(http))


def test_discovery_endpoints_must_be_https():
    with pytest.raises(ProviderUnavailableError, match="https"):
        parse_metadata(
            PROVIDER,
            {
                "issuer": ISSUER,
                "authorization_endpoint": "http://idp.example/authorize",
                "token_endpoint": f"{ISSUER}/token",
                "jwks_uri": f"{ISSUER}/jwks",
            },
        )


@pytest.mark.parametrize(
    ("value", "expected"),
    [
        (None, ()),
        ("admins", ("admins",)),
        (["a", "b", 3], ("a", "b", "3")),
        ({"readers": {"org": "x"}, "writers": {}}, ("readers", "writers")),
        (42, ()),
    ],
)
def test_groups_claims_of_every_shape(value, expected):
    assert claim_values(value) == expected


def test_a_dotted_groups_claim_reads_a_nested_claim(http, clock):
    provider = IdentityProvider(
        name="kc", issuer=ISSUER, client_id="abi", groups_claim="realm_access.roles"
    )
    v, _ = verifier(http, clock, provider)
    verified = v.verify(token(http, realm_access={"roles": ["editor"]}))
    assert verified.groups == ("editor",)


def test_an_email_counts_as_verified_only_when_said_so_or_trusted(http, clock):
    v, _ = verifier(http, clock)
    assert not v.verify(token(http, email="a@acme.test")).email_verified
    trusting = IdentityProvider(
        name="entra", issuer=ISSUER, client_id="abi", trust_email=True
    )
    t, _ = verifier(http, clock, trusting)
    assert t.verify(token(http, email="a@acme.test")).email_verified
    assert not t.verify(token(http)).email_verified
