import asyncio

import pytest
from naas_abi_core.engine.call_context import CallContext, service_account
from naas_abi_core.engine.nats_auth import InvalidServiceTokenError
from naas_abi_core.engine.nats_identity import (
    OnBehalfOfRefusedError,
    caller_context,
    for_request,
)
from naas_abi_core.engine.nats_rpc import authenticate_request
from naas_abi_core.engine.nats_test_tokens import OTHER_TOKENS, TEST_TOKENS
from naas_abi_proto.common.v1 import common_pb2
from naas_abi_proto.dataset.v1 import dataset_pb2
from naas_abi_proto.keyvalue.v1 import keyvalue_pb2
from naas_abi_proto.transfer.v1 import transfer_pb2

SECRET = TEST_TOKENS.verifier
AGENTS = TEST_TOKENS.verifier
SERVICE_ONLY = TEST_TOKENS.verifier_for(("abi:nats",))


def headers(identity: str, **extra: str) -> dict[str, str]:
    return {"Nats-Auth-Token": TEST_TOKENS.token(identity), **extra}


def test_the_caller_is_the_tokens_subject():
    context = caller_context(headers("people"), SECRET)
    assert context.principal == service_account("people")
    assert context.on_behalf_of is None
    assert context.audience == "abi:nats" and context.token_id


def test_the_principal_is_the_id_iam_issued_the_token_for():
    token = TEST_TOKENS.token(
        "module/acme/people", subject="sa_01jabcdefghjkmnpqrstvwxyz0"
    )
    context = caller_context({"Nats-Auth-Token": token}, SECRET)
    assert context.principal.id == "sa_01jabcdefghjkmnpqrstvwxyz0"
    assert context.principal.name == "module/acme/people"


def test_an_actor_claim_acts_for_the_tokens_user_with_its_groups():
    token = TEST_TOKENS.token(
        "usr_01jabcdefghjkmnpqrstvwxyz0",
        kind="user",
        audience="abi:delegated:agent",
        actor="sa_01jabcdefghjkmnpqrstvwxyz1",
        actor_name="api",
        groups=("grp_01jabcdefghjkmnpqrstvwxyz0",),
    )
    context = caller_context({"Nats-Auth-Token": token}, AGENTS)
    assert context.principal.id == "sa_01jabcdefghjkmnpqrstvwxyz1"
    # The actor's account name travels in the token: services that ask whether
    # a first party vouches for the user are told by it.
    assert context.principal.name == "api"
    assert context.on_behalf_of.id == "usr_01jabcdefghjkmnpqrstvwxyz0"
    assert context.on_behalf_of.groups == frozenset({"grp_01jabcdefghjkmnpqrstvwxyz0"})
    assert context.audience == "abi:delegated:agent"
    assert context.token_issued_at is not None
    # The token names its user: no header may name one, from anyone.
    with pytest.raises(OnBehalfOfRefusedError):
        caller_context(
            {"Nats-Auth-Token": token, "Abi-On-Behalf-Of": "usr-ada"}, AGENTS
        )


def test_a_delegated_token_is_refused_where_only_service_tokens_are_accepted():
    token = TEST_TOKENS.token(
        "usr_01jabcdefghjkmnpqrstvwxyz0",
        kind="user",
        audience="abi:delegated:agent",
        actor="sa_01jabcdefghjkmnpqrstvwxyz1",
    )
    with pytest.raises(InvalidServiceTokenError):
        caller_context({"Nats-Auth-Token": token}, SERVICE_ONLY)


@pytest.mark.parametrize(
    "audience",
    [
        "abi:session",
        "abi:delegated:app",
        "abi:delegated:preview",
        "abi:delegated:coding",
        "abi:delegated:api-key",
    ],
)
def test_no_other_delegated_token_reaches_a_kernel_endpoint(audience):
    token = TEST_TOKENS.token(
        "usr_01jabcdefghjkmnpqrstvwxyz0", kind="user", audience=audience
    )
    with pytest.raises(InvalidServiceTokenError):
        caller_context({"Nats-Auth-Token": token}, AGENTS)


def test_a_module_token_named_api_by_a_foreign_issuer_is_refused():
    with pytest.raises(InvalidServiceTokenError):
        caller_context({"Nats-Auth-Token": OTHER_TOKENS.token("api")}, SECRET)


@pytest.mark.parametrize("identity", ["api", "engine", "people"])
def test_the_on_behalf_of_header_is_refused_from_every_identity(identity):
    # A header naming a user can only narrow a call: dropping it would widen
    # it, so it is refused, even from the identities that once sent it.
    with pytest.raises(OnBehalfOfRefusedError, match="delegated token"):
        caller_context(headers(identity, **{"Abi-On-Behalf-Of": "usr-ada"}), SECRET)
    with pytest.raises(OnBehalfOfRefusedError):
        caller_context(headers(identity, **{"abi-on-behalf-of": "usr-ada"}), SECRET)


def test_an_empty_header_names_nobody():
    context = caller_context(headers("api", **{"Abi-On-Behalf-Of": ""}), SECRET)
    assert context.on_behalf_of is None


@pytest.mark.parametrize(
    "sent",
    [
        {},
        {"Nats-Auth-Token": "not-a-token"},
        {"Nats-Auth-Token": OTHER_TOKENS.token("api")},
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
    assert caller.principal == service_account("api")
    assert caller.on_behalf_of is None
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
    assert any("Abi-On-Behalf-Of" in line for line in seen)


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
