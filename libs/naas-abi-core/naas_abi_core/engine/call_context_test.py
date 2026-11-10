from pathlib import Path

import naas_abi_sdk.call_context as sdk
from naas_abi_core.engine import call_context_types
from naas_abi_core.engine.call_context import (
    CallContext,
    as_service_account,
    current_call_context,
    service_account,
    use_call_context,
    user,
)

# The container a call is made in: request data, carried as is.
WS = "abi:nexus:organization/org-1/nexus:workspace/ws-1"


def test_the_engine_and_the_sdk_share_one_context():
    caller = CallContext(principal=service_account("api"), on_behalf_of=user("usr-ada"))
    with use_call_context(caller):
        assert sdk.current_call_context() is caller
    with sdk.use_call_context(caller):
        assert current_call_context() is caller


def test_as_service_account_acts_for_nobody_and_keeps_the_target():
    caller = CallContext(
        principal=service_account("api"),
        on_behalf_of=user("usr-ada"),
        audience="abi:nats",
        token_id="jti-1",
        scope=({"effect": "Allow"},),
        container=WS,
        trace_id="trace-1",
    )
    with use_call_context(caller), as_service_account("engine") as engine:
        assert current_call_context() is engine
        assert engine.principal == service_account("engine")
        assert engine.user is None
        assert (engine.audience, engine.token_id, engine.scope) == (None, None, None)
        assert (engine.container, engine.trace_id) == (WS, "trace-1")
        assert current_call_context() is engine
    assert current_call_context() == sdk.ANONYMOUS


def test_the_copy_for_installs_without_the_sdk_is_verbatim():
    assert (
        Path(call_context_types.__file__).read_text() == Path(sdk.__file__).read_text()
    )
