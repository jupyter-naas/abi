from datetime import UTC, datetime, timedelta

import pytest
from naas_abi_core.engine.nats_auth import (
    InvalidServiceTokenError,
    issue_service_token,
)
from naas_abi_core.engine.nats_identity import OnBehalfOfRefusedError
from naas_abi_core.services.discovery.caller import caller_of, run_owner

SECRET = "discovery-caller-test-secret-32-bytes"


def test_a_forwarded_caller_is_verified_like_a_kernel_endpoints():
    token = issue_service_token("api", SECRET)
    caller = caller_of(token, "user-1", SECRET)
    assert (caller.principal.id, caller.user.id) == ("api", "user-1")
    assert run_owner(caller) == "user-1"
    module = caller_of(issue_service_token("research", SECRET), "", SECRET)
    assert run_owner(module) == "research"
    with pytest.raises(OnBehalfOfRefusedError):
        caller_of(issue_service_token("research", SECRET), "user-1", SECRET)
    with pytest.raises(InvalidServiceTokenError):
        caller_of(
            issue_service_token("api", "another-secret-of-32-bytes!!"), "", SECRET
        )


def test_a_stored_trigger_is_checked_as_of_when_it_was_stored():
    issued = datetime.now(UTC) - timedelta(days=2)
    token = issue_service_token("api", SECRET, ttl=timedelta(hours=1), now=issued)
    with pytest.raises(InvalidServiceTokenError):
        caller_of(token, "user-1", SECRET)  # expired now
    stored = (issued + timedelta(minutes=5)).timestamp()
    assert caller_of(token, "user-1", SECRET, at=stored).user.id == "user-1"
    with pytest.raises(InvalidServiceTokenError):  # stored after it expired
        caller_of(token, "", SECRET, at=(issued + timedelta(hours=2)).timestamp())
    with pytest.raises(InvalidServiceTokenError):  # stored before it was issued
        caller_of(token, "", SECRET, at=(issued - timedelta(hours=1)).timestamp())
    with pytest.raises(OnBehalfOfRefusedError):
        caller_of(
            issue_service_token("research", SECRET, now=issued),
            "user-1",
            SECRET,
            at=stored,
        )
