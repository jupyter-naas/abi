import asyncio
from types import SimpleNamespace
from typing import ClassVar
from unittest.mock import AsyncMock, Mock

import pytest
from naas_abi_proto.common.v1 import common_pb2
from naas_abi_proto.dataset.v1 import dataset_pb2
from naas_abi_proto.keyvalue.v1 import keyvalue_pb2 as kv
from naas_abi_proto.transfer.v1 import transfer_pb2 as pb
from nats.errors import NoRespondersError
from overflow_fakes import OWNER, FakeHost

from naas_abi_sdk.call_context import (
    CallContext,
    service_account,
    use_call_context,
    user,
)
from naas_abi_sdk.transport import RPCError, Transport


def transport(reply=b"", headers=None, **options):
    rpc = Transport("nats://unused", "issued-token", timeout=0.02, **options)
    nc = SimpleNamespace(
        max_payload=8 * 1024 * 1024,
        request=AsyncMock(return_value=SimpleNamespace(data=reply, headers=headers)),
    )
    rpc.connect = AsyncMock(return_value=nc)
    return rpc, nc


def test_roundtrip_preserves_bytes_and_does_not_mutate_request():
    rpc, nc = transport(kv.GetResponse(value=b"\x00\xff").SerializeToString())
    request = kv.GetRequest(key="demo")
    result = asyncio.run(rpc.call("abi.svc.keyvalue.v1.get", request, kv.GetResponse))
    assert result.value == b"\x00\xff"
    assert not request.HasField("context")
    sent = kv.GetRequest.FromString(nc.request.call_args.args[1])
    assert sent.context.trace_id and sent.context.timeout_ms == 20
    assert nc.request.call_args.kwargs["headers"] == {
        "Nats-Auth-Token": "issued-token",
        "Abi-Overflow": "1",  # can read a reply above the broker limit
    }


def test_the_current_calls_trace_and_workspace_travel_with_the_call():
    rpc, nc = transport(kv.GetResponse().SerializeToString())
    caller = CallContext(
        principal=service_account("api"),
        on_behalf_of=user("usr-ada"),
        workspace_id="ws-1",
        trace_id="trace-1",
    )
    with use_call_context(caller):
        asyncio.run(
            rpc.call("abi.svc.keyvalue.v1.get", kv.GetRequest(), kv.GetResponse)
        )
    sent = kv.GetRequest.FromString(nc.request.call_args.args[1])
    assert (sent.context.trace_id, sent.context.workspace_id) == ("trace-1", "ws-1")
    # Identity travels only in headers, never in the request body.
    assert not sent.context.principal_id and not sent.context.tenant_id


def test_a_delegating_transport_sends_the_token_that_carries_the_user():
    seen = []

    def delegate(who, recipient):
        seen.append((who.id, recipient))
        return f"delegation-for-{who.id}"

    rpc, nc = transport(kv.GetResponse().SerializeToString(), delegate=delegate)
    caller = CallContext(principal=service_account("api"), on_behalf_of=user("usr-ada"))
    with use_call_context(caller):
        asyncio.run(
            rpc.call("abi.svc.keyvalue.v1.get", kv.GetRequest(), kv.GetResponse)
        )
    headers = nc.request.call_args.kwargs["headers"]
    assert headers["Nats-Auth-Token"] == "delegation-for-usr-ada"
    assert "Abi-On-Behalf-Of" not in headers
    assert seen == [("usr-ada", None)]


def test_a_delegate_may_be_asynchronous_and_names_the_host_it_calls():
    seen = []

    async def delegate(who, recipient):
        seen.append(recipient)
        return "delegation-for-a-host"

    rpc, nc = transport(kv.GetResponse().SerializeToString(), delegate=delegate)
    caller = CallContext(principal=service_account("api"), on_behalf_of=user("usr-ada"))
    with use_call_context(caller):
        asyncio.run(
            rpc.call(
                "abi.agent.default.HOSTULID.i1.summarize.submit",
                kv.GetRequest(),
                kv.GetResponse,
            )
        )
    assert seen == ["HOSTULID"]
    assert nc.request.call_args.kwargs["headers"]["Nats-Auth-Token"] == (
        "delegation-for-a-host"
    )


def test_without_a_user_the_transport_calls_as_itself():
    rpc, nc = transport(
        kv.GetResponse().SerializeToString(),
        delegate=lambda who, recipient: pytest.fail("no user to carry"),
    )
    with use_call_context(CallContext(principal=service_account("engine"))):
        asyncio.run(
            rpc.call("abi.svc.keyvalue.v1.get", kv.GetRequest(), kv.GetResponse)
        )
    assert nc.request.call_args.kwargs["headers"]["Nats-Auth-Token"] == "issued-token"


def test_a_delegation_that_fails_fails_the_call_instead_of_dropping_the_user():
    def refuse(who, recipient):
        raise PermissionError("user suspended")

    rpc, nc = transport(kv.GetResponse().SerializeToString(), delegate=refuse)
    caller = CallContext(principal=service_account("api"), on_behalf_of=user("usr-ada"))
    with use_call_context(caller), pytest.raises(PermissionError):
        asyncio.run(
            rpc.call("abi.svc.keyvalue.v1.get", kv.GetRequest(), kv.GetResponse)
        )
    nc.request.assert_not_called()


def test_a_transport_without_a_delegate_calls_as_itself_for_any_user():
    """A module's transport calls as the module: it is not allowed to carry a user."""
    rpc, nc = transport(kv.GetResponse().SerializeToString())
    caller = CallContext(principal=service_account("api"), on_behalf_of=user("u"))
    with use_call_context(caller):
        asyncio.run(
            rpc.call("abi.svc.keyvalue.v1.get", kv.GetRequest(), kv.GetResponse)
        )
    headers = nc.request.call_args.kwargs["headers"]
    assert headers["Nats-Auth-Token"] == "issued-token"
    assert "Abi-On-Behalf-Of" not in headers


def _jwt(exp, **claims):
    import base64
    import json

    body = base64.urlsafe_b64encode(json.dumps({"exp": exp, **claims}).encode())
    return f"h.{body.decode().rstrip('=')}.s"


def test_a_run_makes_its_kernel_calls_with_the_delegation_it_was_handed():
    import time

    token = _jwt(time.time() + 600)
    rpc, nc = transport(kv.GetResponse().SerializeToString())
    context = CallContext(
        principal=service_account("module/acme/people"),
        on_behalf_of=user("usr-ada"),
        delegated_token=token,
    )
    with use_call_context(context):
        asyncio.run(
            rpc.call("abi.svc.keyvalue.v1.get", kv.GetRequest(), kv.GetResponse)
        )
    assert nc.request.call_args.kwargs["headers"]["Nats-Auth-Token"] == token


def test_a_run_never_hands_its_delegation_to_another_module_host():
    import time

    rpc, nc = transport(kv.GetResponse().SerializeToString())
    context = CallContext(
        principal=service_account("module/acme/people"),
        on_behalf_of=user("usr-ada"),
        delegated_token=_jwt(time.time() + 600),
    )
    with use_call_context(context):
        rpc.host_token = lambda recipient: f"host-token-{recipient}"
        asyncio.run(
            rpc.call(
                "abi.agent.default.OTHERHOST.i1.x.submit",
                kv.GetRequest(),
                kv.GetResponse,
            )
        )
    # The host gets this module's own token for it, not the user's delegation.
    assert nc.request.call_args.kwargs["headers"]["Nats-Auth-Token"] == (
        "host-token-OTHERHOST"
    )


def test_a_delegation_about_to_expire_is_renewed_through_the_service_key():
    import time

    old = _jwt(time.time() + 10)
    fresh = _jwt(time.time() + 600)
    rpc, nc = transport(kv.GetResponse().SerializeToString())
    renewed = []

    class Credentials:
        async def renew_delegation(self, transport, token):
            renewed.append(token)
            return fresh

        async def access_token(self, transport, audience="abi:nats"):
            return "issued-token"

    rpc.credentials = Credentials()
    context = CallContext(
        principal=service_account("module/acme/people"),
        on_behalf_of=user("usr-ada"),
        delegated_token=old,
    )

    async def twice():
        for _ in range(2):
            await rpc.call("abi.svc.keyvalue.v1.get", kv.GetRequest(), kv.GetResponse)

    with use_call_context(context):
        asyncio.run(twice())
    assert renewed == [old]  # once, then remembered
    assert nc.request.call_args.kwargs["headers"]["Nats-Auth-Token"] == fresh


def test_a_request_keeps_its_own_trace_and_workspace():
    rpc, nc = transport(kv.GetResponse().SerializeToString())
    request = kv.GetRequest(
        context=common_pb2.CallContext(trace_id="mine", workspace_id="ws-2")
    )
    with use_call_context(
        CallContext(principal=service_account("api"), workspace_id="ws-1")
    ):
        asyncio.run(rpc.call("abi.svc.keyvalue.v1.get", request, kv.GetResponse))
    sent = kv.GetRequest.FromString(nc.request.call_args.args[1])
    assert (sent.context.trace_id, sent.context.workspace_id) == ("mine", "ws-2")
    assert "Abi-On-Behalf-Of" not in nc.request.call_args.kwargs["headers"]


@pytest.mark.parametrize("error", [TimeoutError(), ConnectionError("lost")])
def test_mutations_are_never_replayed(error):
    rpc, nc = transport()
    nc.request.side_effect = error
    with pytest.raises(type(error)):
        asyncio.run(rpc.call("set", kv.SetRequest(key="k", value=b"v"), kv.SetResponse))
    assert nc.request.await_count == 1


def test_deadline_cancels_local_wait():
    rpc, nc = transport()
    cancelled = []

    async def wait(*args, **kwargs):
        try:
            await asyncio.sleep(10)
        finally:
            cancelled.append(True)

    nc.request.side_effect = wait
    with pytest.raises(asyncio.TimeoutError):
        asyncio.run(rpc.call("set", kv.SetRequest(), kv.SetResponse))
    assert cancelled == [True]
    assert nc.request.await_count == 1


def test_empty_success_and_error_headers_are_distinct():
    rpc, _ = transport()
    asyncio.run(rpc.call("set", kv.SetRequest(), kv.SetResponse))
    rpc, _ = transport(
        headers={"Nats-Service-Error-Code": "401", "Nats-Service-Error": "Unauthorized"}
    )
    with pytest.raises(RPCError, match="401"):
        asyncio.run(rpc.call("set", kv.SetRequest(), kv.SetResponse))


def test_nested_domain_error_retains_structured_details():
    response = dataset_pb2.DescribeResponse(
        error=dataset_pb2.DatasetError(
            error=common_pb2.CallError(code="NOT_FOUND", message="missing"),
            not_found=dataset_pb2.DatasetNotFoundDetail(
                name="demo", namespace="default"
            ),
        )
    )
    rpc, _ = transport(response.SerializeToString())
    with pytest.raises(RPCError) as caught:
        asyncio.run(
            rpc.call(
                "describe", dataset_pb2.DescribeRequest(), dataset_pb2.DescribeResponse
            )
        )
    assert caught.value.code == "NOT_FOUND"
    assert caught.value.response.error.not_found.name == "demo"


def test_payload_limit_includes_auth_headers():
    rpc, nc = transport()
    nc.max_payload = 10
    with pytest.raises(RPCError, match="PAYLOAD_TOO_LARGE"):
        asyncio.run(rpc.call("set", kv.SetRequest(), kv.SetResponse))
    nc.request.assert_not_called()


def test_token_provider_is_queried_for_each_call():
    rpc, nc = transport()
    tokens = iter(["first", "second"])
    rpc.token = lambda: next(tokens)

    async def calls():
        for _ in range(2):
            await rpc.call("set", kv.SetRequest(), kv.SetResponse)

    asyncio.run(calls())
    assert [
        c.kwargs["headers"]["Nats-Auth-Token"] for c in nc.request.call_args_list
    ] == ["first", "second"]


def test_closed_client_cannot_reconnect():
    async def close():
        rpc = Transport("nats://unused", "issued")
        await rpc.close()
        with pytest.raises(RuntimeError, match="closed"):
            await rpc.connect()

    asyncio.run(close())


# --- overflow: payloads above the broker limit (docs/adr/20261003_nats-rpc-overflow.md)


class OverflowBroker:
    """A broker whose overflow subjects reach FakeHost and the rest a service."""

    OPERATIONS: ClassVar[dict[str, type]] = {
        "open": pb.OpenRequest,
        "write": pb.WriteRequest,
        "read": pb.ReadRequest,
        "close": pb.CloseRequest,
    }

    def __init__(self, host, service, max_payload=8 * 1024 * 1024, overflow=True):
        self.host, self.service, self.overflow = host, service, overflow
        self.max_payload = max_payload
        self.sent = []

    async def request(self, subject, payload, headers=None, timeout=None):
        self.sent.append((subject, payload, dict(headers or {})))
        if subject.startswith("abi.rpc.overflow."):
            if not self.overflow:
                raise NoRespondersError()
            request = self.OPERATIONS[subject.rsplit(".", 1)[1]].FromString(payload)
            reply = await self.host.call(subject, request, None)
            return SimpleNamespace(data=reply.SerializeToString(), headers=None)
        return self.service(payload, headers or {})


def overflow_transport(broker):
    rpc = Transport("nats://unused", "issued-token", timeout=1)
    rpc.connect = AsyncMock(return_value=broker)
    return rpc


def test_an_overflowed_reply_is_downloaded_and_decoded():
    value = bytes(range(256)) * 40
    reply = kv.GetResponse(value=value).SerializeToString()
    host = FakeHost(parked=reply, chunk_bytes=1024)
    broker = OverflowBroker(
        host,
        lambda payload, headers: SimpleNamespace(
            data=b"",
            headers={
                "Abi-Overflow-Reply": f"{OWNER}:3",
                "Abi-Overflow-Size": str(len(reply)),
            },
        ),
    )

    result = asyncio.run(
        overflow_transport(broker).call(
            "abi.svc.keyvalue.v1.get", kv.GetRequest(key="k"), kv.GetResponse
        )
    )

    assert result.value == value
    assert host.closed == [f"{OWNER}:3"]
    assert all(h["Nats-Auth-Token"] == "issued-token" for _, _, h in broker.sent)


def test_a_request_above_the_broker_limit_is_uploaded_before_the_call():
    received = []

    def service(payload, headers):
        received.append((payload, headers))
        return SimpleNamespace(data=kv.SetResponse().SerializeToString(), headers=None)

    host = FakeHost(chunk_bytes=1024)
    broker = OverflowBroker(host, service, max_payload=4096)
    request = kv.SetRequest(key="k", value=b"x" * 10_000)

    asyncio.run(
        overflow_transport(broker).call(
            "abi.svc.keyvalue.v1.set", request, kv.SetResponse
        )
    )

    ((payload, headers),) = received
    transfer_id = headers["Abi-Overflow-Request"]
    assert payload == b""
    sent = kv.SetRequest.FromString(bytes(host.uploads[transfer_id]))
    assert (sent.key, sent.value) == ("k", b"x" * 10_000)
    assert host.closed == [transfer_id]  # released once the call returned


def test_an_engine_without_overflow_still_refuses_a_large_request():
    service = Mock()
    broker = OverflowBroker(FakeHost(), service, max_payload=4096, overflow=False)

    with pytest.raises(RPCError) as raised:
        asyncio.run(
            overflow_transport(broker).call(
                "abi.svc.keyvalue.v1.set",
                kv.SetRequest(value=b"x" * 10_000),
                kv.SetResponse,
            )
        )

    assert raised.value.code == "PAYLOAD_TOO_LARGE"
    service.assert_not_called()


def test_the_brokers_limit_is_the_only_limit():
    # A broker configured above 8 MiB carries a 10 MiB call in one message.
    rpc, nc = transport(kv.SetResponse().SerializeToString())
    nc.max_payload = 16 * 1024 * 1024
    asyncio.run(
        rpc.call(
            "set",
            kv.SetRequest(key="k", value=b"x" * (10 * 1024 * 1024)),
            kv.SetResponse,
        )
    )
    (subject, payload), _ = nc.request.call_args
    assert subject == "set" and len(payload) > 10 * 1024 * 1024


def _sent_token(nc):
    return nc.request.call_args.kwargs["headers"]["Nats-Auth-Token"]


def test_a_call_to_a_host_carries_a_token_for_that_host_only():
    """A host reads its caller's token: it is never the one the kernel accepts,
    nor one made for another host."""
    rpc, nc = transport(
        kv.GetResponse().SerializeToString(),
        host_token=lambda recipient: f"for-{recipient}",
    )
    for subject, recipient in (
        ("abi.agent.default.SAONE.i.h.v1.submit", "SAONE"),
        ("abi.mod.default.SATWO.i.model.m.chat", "SATWO"),
    ):
        asyncio.run(rpc.call(subject, kv.GetRequest(key="x"), kv.GetResponse))
        assert _sent_token(nc) == f"for-{recipient}", subject
    for subject in ("abi.svc.keyvalue.v1.get", "abi.discovery.default.v1.list_modules"):
        asyncio.run(rpc.call(subject, kv.GetRequest(key="x"), kv.GetResponse))
        assert _sent_token(nc) == "issued-token", subject


def test_the_host_a_subject_addresses():
    from naas_abi_sdk.transport import host_recipient

    assert host_recipient("abi.agent.default.SA.inst.digest.v1.submit") == "SA"
    assert host_recipient("abi.mod.default.SA.inst.app.x.http") == "SA"
    assert host_recipient("abi.svc.keyvalue.v1.get") is None
    assert host_recipient("abi.agent.default") is None


def test_a_transport_without_a_host_token_makes_no_call_to_a_host():
    from naas_abi_sdk.transport import NoHostTokenError

    rpc, nc = transport(kv.GetResponse().SerializeToString())
    with pytest.raises(NoHostTokenError):
        asyncio.run(
            rpc.call(
                "abi.agent.default.sa.i.h.v1.submit", kv.GetRequest(), kv.GetResponse
            )
        )
    nc.request.assert_not_called()
