from datetime import UTC, datetime, timedelta

import pytest
from naas_abi_core.engine.nats_auth import InvalidServiceTokenError
from naas_abi_core.engine.nats_identity import OnBehalfOfRefusedError
from naas_abi_core.engine.nats_test_tokens import TEST_TOKENS, TestTokens
from naas_abi_core.services.discovery.caller import caller_of, run_owner

VERIFIER = TEST_TOKENS.verifier


def test_a_forwarded_caller_is_verified_like_a_kernel_endpoints():
    caller = caller_of(TEST_TOKENS.token("api"), "user-1", VERIFIER)
    assert (caller.principal.id, caller.user.id) == ("api", "user-1")
    assert run_owner(caller) == "user-1"
    module = caller_of(TEST_TOKENS.token("research"), "", VERIFIER)
    assert run_owner(module) == "research"
    with pytest.raises(OnBehalfOfRefusedError):
        caller_of(TEST_TOKENS.token("research"), "user-1", VERIFIER)
    with pytest.raises(InvalidServiceTokenError):
        caller_of(TestTokens().token("api"), "", VERIFIER)  # another issuer


def test_a_stored_trigger_is_checked_as_of_when_it_was_stored():
    issued = datetime.now(UTC) - timedelta(days=2)
    token = TEST_TOKENS.token("api", issued_at=int(issued.timestamp()))
    with pytest.raises(InvalidServiceTokenError):
        caller_of(token, "user-1", VERIFIER)  # expired now
    stored = (issued + timedelta(minutes=5)).timestamp()
    assert caller_of(token, "user-1", VERIFIER, at=stored).user.id == "user-1"
    with pytest.raises(InvalidServiceTokenError):  # stored after it expired
        caller_of(token, "", VERIFIER, at=(issued + timedelta(hours=2)).timestamp())
    with pytest.raises(InvalidServiceTokenError):  # stored before it was issued
        caller_of(token, "", VERIFIER, at=(issued - timedelta(hours=1)).timestamp())
    with pytest.raises(OnBehalfOfRefusedError):
        caller_of(
            TEST_TOKENS.token("research", issued_at=int(issued.timestamp())),
            "user-1",
            VERIFIER,
            at=stored,
        )
