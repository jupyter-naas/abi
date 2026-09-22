import asyncio
from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest
from naas_abi_proto.common.v1 import common_pb2
from naas_abi_proto.dataset.v1 import dataset_pb2
from naas_abi_proto.keyvalue.v1 import keyvalue_pb2 as kv

from naas_abi_sdk.transport import RPCError, Transport


def transport(reply=b"", headers=None):
    rpc = Transport("nats://unused", "issued-token", timeout=0.02)
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
    assert nc.request.call_args.kwargs["headers"] == {"Nats-Auth-Token": "issued-token"}


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
