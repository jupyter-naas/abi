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


def test_the_environment_gives_the_module_key_else_an_issued_token():
    """The key wins: it signs fresh tokens and binds them to the module called."""
    both = token_from_env({"ABI_SERVICE_TOKEN": "t", "ABI_MODULE_KEY": "k"}, "m")
    assert isinstance(both, ModuleToken) and both.identity == "m"
    assert token_from_env({"ABI_SERVICE_TOKEN": "t"}, "m") == "t"
    source = token_from_env({"ABI_MODULE_KEY": "k"}, "acme.research")
    assert isinstance(source, ModuleToken) and source.identity == "acme.research"
    with pytest.raises(RuntimeError, match="abi module key acme.research"):
        token_from_env({"NATS_JWT_SECRET": "s"}, "acme.research")


def test_a_token_bound_to_an_instance_is_short_and_good_there_only():
    nats_auth = pytest.importorskip("naas_abi_core.engine.nats_auth")
    secret = "s" * 48
    token = ModuleToken("acme.research", nats_auth.module_key(secret, "acme.research"))
    bound = token.for_audience("i-1")

    _, claims = _parts(bound)
    assert claims["aud"] == "i-1" and claims["exp"] - claims["iat"] == 300
    assert nats_auth.verify_service_token(bound, secret, audience="i-1") == "acme.research"
    with pytest.raises(nats_auth.InvalidServiceTokenError):
        nats_auth.verify_service_token(bound, secret)
    assert "aud" not in _parts(token())[1]


def test_the_transport_binds_calls_to_modules_and_only_those():
    from naas_abi_sdk.transport import Transport, is_module_subject

    assert is_module_subject("abi.agent.acme.i-1.d1.v1.submit")
    assert is_module_subject("abi.mod.acme.i-2.app.console.http")
    assert not is_module_subject("abi.svc.document.v1.get")
    assert not is_module_subject("abi.discovery.acme.v1.register")
    token = ModuleToken("m", "k")
    transport = Transport("nats://127.0.0.1:4222", token)
    bound = transport._token("abi.mod.acme.i-2.app.x.http", "i-2")
    assert _parts(bound)[1]["aud"] == "i-2"
    assert "aud" not in _parts(transport._token("abi.svc.document.v1.get"))[1]
    with pytest.raises(ValueError, match="bound"):
        Transport("nats://127.0.0.1:4222", "static")._token(
            "abi.mod.acme.i-2.app.x.http", "i-2"
        )
    # The caller names the instance: a call to a module without it is refused.
    with pytest.raises(ValueError, match="instance_id"):
        transport._token("abi.mod.acme.i-2.app.x.http")


def test_a_dotted_instance_id_cannot_borrow_another_instances_audience():
    """An instance registered as ``<B>.x`` would put B's id where the subject's
    instance token is: the token must stay bound to the id the caller passed."""
    from naas_abi_sdk.transport import Transport

    transport = Transport("nats://127.0.0.1:4222", ModuleToken("m", "k"))
    with pytest.raises(ValueError):
        transport._token("abi.mod.acme.instance-b.x.app.console.http", "instance-b.x")
    with pytest.raises(ValueError, match="does not address"):
        transport._token("abi.mod.acme.instance-b.x.app.console.http", "x")


def test_a_module_login_uses_the_module_inbox_prefix():
    from naas_abi_sdk.transport import MODULE_INBOX_PREFIX, Transport

    assert (
        Transport("nats://module:pw@nats:4222", "t").options["inbox_prefix"]
        == MODULE_INBOX_PREFIX
    )
    assert "inbox_prefix" not in Transport("nats://abi:pw@nats:4222", "t").options


def test_a_bound_token_is_reused_only_while_fresh():
    from naas_abi_sdk.service_token import BOUND_REUSE_SECONDS

    now = [1000.0]
    token = ModuleToken("m", "k", clock=lambda: now[0])
    first = token.for_audience("i-1")
    now[0] += BOUND_REUSE_SECONDS - 1
    assert token.for_audience("i-1") == first
    now[0] += 2
    fresh = token.for_audience("i-1")
    assert fresh != first and _parts(fresh)[1]["iat"] == int(now[0])
