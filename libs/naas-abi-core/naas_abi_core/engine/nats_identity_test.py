import asyncio

import pytest
from naas_abi_core.engine.call_context import CallContext, service_account, user
from naas_abi_core.engine.nats_auth import InvalidServiceTokenError, issue_service_token
from naas_abi_core.engine.nats_identity import (
    OnBehalfOfRefusedError,
    caller_context,
    for_request,
)
from naas_abi_core.engine.nats_rpc import authenticate_request
from naas_abi_proto.common.v1 import common_pb2
from naas_abi_proto.dataset.v1 import dataset_pb2
from naas_abi_proto.keyvalue.v1 import keyvalue_pb2
from naas_abi_proto.transfer.v1 import transfer_pb2

SECRET = "nats-identity-test-secret-32-bytes!"


def headers(identity: str, **extra: str) -> dict[str, str]:
    return {"Nats-Auth-Token": issue_service_token(identity, SECRET), **extra}


def test_the_caller_is_the_tokens_subject():
    assert caller_context(headers("people"), SECRET) == CallContext(
        principal=service_account("people")
    )


@pytest.mark.parametrize("identity", ["api", "engine"])
def test_a_trusted_identity_may_name_the_user_it_acts_for(identity):
    context = caller_context(
        headers(identity, **{"Abi-On-Behalf-Of": "usr-ada"}), SECRET
    )
    assert context.principal == service_account(identity)
    assert context.on_behalf_of == user("usr-ada")
    assert context.user == user("usr-ada")


def test_no_other_identity_may_name_a_user():
    with pytest.raises(OnBehalfOfRefusedError):
        caller_context(headers("people", **{"Abi-On-Behalf-Of": "usr-ada"}), SECRET)


@pytest.mark.parametrize("named", [" usr-ada", "u" * 257])
def test_a_malformed_user_is_refused(named):
    with pytest.raises(OnBehalfOfRefusedError):
        caller_context(headers("api", **{"Abi-On-Behalf-Of": named}), SECRET)


@pytest.mark.parametrize(
    "sent",
    [
        {},
        {"Nats-Auth-Token": "not-a-token"},
        {
            "Nats-Auth-Token": issue_service_token(
                "api", "another-secret-32-bytes-long!!"
            )
        },
    ],
)
def test_without_a_valid_token_there_is_no_caller(sent):
    with pytest.raises(InvalidServiceTokenError):
        caller_context(sent, SECRET)


class _Request:
    def __init__(self, sent):
        self.headers = sent
        self.data = b""
        self.replies: list[bytes] = []

    async def respond(self, data=b"", headers=None):
        self.replies.append(data)


def _authenticate(sent, response_cls=keyvalue_pb2.GetResponse):
    request = _Request(sent)
    caller = asyncio.run(authenticate_request(request, SECRET, response_cls))
    return caller, [response_cls.FromString(reply) for reply in request.replies]


def test_authenticate_request_hands_back_the_caller_and_answers_nothing():
    caller, replies = _authenticate(headers("api"))
    assert caller == CallContext(principal=service_account("api"))
    assert replies == []


def test_a_bad_token_is_answered_unauthenticated():
    caller, [reply] = _authenticate(None)
    assert caller is None
    assert (reply.error.code, reply.error.message, reply.error.retryable) == (
        "UNAUTHENTICATED",
        "missing or invalid auth token",
        False,
    )


def test_a_refused_user_is_answered_and_logged_as_such():
    from naas_abi_core import logger

    seen: list[str] = []
    handler = logger.add(lambda message: seen.append(str(message)), level="WARNING")
    try:
        caller, [reply] = _authenticate(
            headers("people", **{"Abi-On-Behalf-Of": "usr-ada"}),
            dataset_pb2.DescribeResponse,  # a domain error wrapping the CallError
        )
    finally:
        logger.remove(handler)
    assert caller is None
    assert reply.error.error.code == "UNAUTHENTICATED"
    assert reply.error.error.message.startswith("on-behalf-of refused")
    assert any("naming a user" in line for line in seen)


def test_trace_and_workspace_come_from_the_request_but_identity_never_does():
    caller = CallContext(principal=service_account("api"))
    request = keyvalue_pb2.GetRequest(
        context=common_pb2.CallContext(
            trace_id="trace-1",
            workspace_id="ws-1",
            principal_id="usr-mallory",  # reserved: never read
            tenant_id="tenant-x",
        )
    )
    assert for_request(caller, request) == CallContext(
        principal=service_account("api"), workspace_id="ws-1", trace_id="trace-1"
    )


def test_a_request_without_an_envelope_keeps_the_caller():
    caller = CallContext(principal=service_account("api"), trace_id="t")
    assert for_request(caller, keyvalue_pb2.GetRequest()) == caller
    assert for_request(caller, object()) is caller
    opened = transfer_pb2.OpenRequest(context=common_pb2.CallContext(trace_id="t2"))
    assert for_request(caller, opened).trace_id == "t2"
