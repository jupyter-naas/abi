import json

import pytest
from naas_abi_sdk.service_token import ModuleToken, token_from_env


def _parts(token):
    import base64

    def decode(part):
        return json.loads(base64.urlsafe_b64decode(part + "=" * (-len(part) % 4)))

    header, claims, _ = token.split(".")
    return decode(header), decode(claims)


def test_a_module_token_carries_its_identity_and_the_module_header():
    header, claims = _parts(ModuleToken("acme.research", "k" * 43, clock=lambda: 1000)())

    assert header == {"alg": "HS256", "kid": "module", "typ": "JWT"}
    assert claims == {"sub": "acme.research", "iat": 1000, "exp": 4600}


def test_the_engine_accepts_it_for_that_identity_only():
    nats_auth = pytest.importorskip("naas_abi_core.engine.nats_auth")
    secret = "s" * 48
    key = nats_auth.module_key(secret, "acme.research")

    assert nats_auth.verify_service_token(ModuleToken("acme.research", key)(), secret) == "acme.research"
    with pytest.raises(nats_auth.InvalidServiceTokenError):
        nats_auth.verify_service_token(ModuleToken("acme.billing", key)(), secret)
    with pytest.raises(nats_auth.InvalidServiceTokenError):
        nats_auth.verify_service_token(ModuleToken("api", key)(), secret)


def test_it_is_refreshed_at_half_its_lifetime():
    now = [0.0]
    token = ModuleToken("m", "k", ttl_seconds=100, clock=lambda: now[0])
    first = token()
    now[0] = 49
    assert token() == first
    now[0] = 50
    assert token() != first


def test_the_environment_gives_an_issued_token_or_the_module_key():
    assert token_from_env({"ABI_SERVICE_TOKEN": "t", "ABI_MODULE_KEY": "k"}, "m") == "t"
    source = token_from_env({"ABI_MODULE_KEY": "k"}, "acme.research")
    assert isinstance(source, ModuleToken) and source.identity == "acme.research"
    with pytest.raises(RuntimeError, match="abi module key acme.research"):
        token_from_env({"NATS_JWT_SECRET": "s"}, "acme.research")
