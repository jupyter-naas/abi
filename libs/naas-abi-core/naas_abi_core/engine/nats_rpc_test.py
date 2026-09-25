"""Transport guarantees exercised through every concrete RPC adapter."""

import asyncio
import importlib
from types import SimpleNamespace
from unittest.mock import AsyncMock, Mock

import pytest
from naas_abi_core.engine.nats_auth import issue_service_token
from naas_abi_core.proto.common.v1 import common_pb2
from naas_abi_core.proto.dataset.v1 import dataset_pb2
from naas_abi_core.proto.keyvalue.v1 import keyvalue_pb2
from nats.errors import ConnectionClosedError, MaxPayloadError, NoRespondersError
from nats.errors import TimeoutError as NatsTimeoutError

ADAPTERS = [
    ("activity_log", "ActivityLog"),
    ("cache", "Cache"),
    ("coding_environment", "CodingEnvironment"),
    ("dataset", "Dataset"),
    ("email", "Email"),
    ("event", "Event"),
    ("keyvalue", "KeyValue"),
    ("object_storage", "ObjectStorage"),
    ("secret", "Secret"),
    ("source_control", "SourceControl"),
    ("triple_store", "TripleStore"),
    ("vector_store", "VectorStore"),
]
SECRET = "rpc-test-secret-at-least-32-bytes-long"


def adapter_class(domain, name, primary=False):
    directory = "adaptors" if domain == "secret" else "adapters"
    if primary:
        module = f"{directory}.primary.{domain}__primary_adapter__NATS"
        name += "PrimaryAdapterNATS"
    else:
        name += "SecondaryAdapterNATSClient"
        module = f"{directory}.secondary.{name}"
    return getattr(
        importlib.import_module(f"naas_abi_core.services.{domain}.{module}"), name
    )


@pytest.fixture(params=ADAPTERS, ids=lambda pair: pair[0])
def client(request, monkeypatch):
    monkeypatch.setattr("nats.connect", AsyncMock(side_effect=ConnectionClosedError()))
    cls = adapter_class(*request.param)
    with cls("nats://unused:4222", SECRET, "test") as instance:
        yield instance


def connection(client, **kwargs):
    nc = SimpleNamespace(
        is_connected=True,
        is_closed=False,
        max_payload=8 * 1024 * 1024,
        request=AsyncMock(**kwargs),
        close=AsyncMock(),
    )
    client._nc = nc
    return nc


def call(client):
    return client._call(
        "abi.test", keyvalue_pb2.GetRequest(key="k"), keyvalue_pb2.GetResponse
    )


@pytest.mark.parametrize(
    "error", [NatsTimeoutError(), ConnectionClosedError(), NoRespondersError()]
)
def test_failed_request_is_never_replayed(client, error):
    nc = connection(client, side_effect=error)
    with pytest.raises(type(error)):
        call(client)
    assert nc.request.await_count == 1
    nc.close.assert_not_awaited()


@pytest.mark.parametrize(
    "headers",
    [
        {"Nats-Service-Error": "reply failed", "Nats-Service-Error-Code": "500"},
        {"Nats-Service-Error-Code": "500"},
        {"Nats-Service-Error": "reply failed"},
    ],
)
def test_micro_error_headers_never_become_empty_success(client, headers):
    nc = connection(client, return_value=SimpleNamespace(data=b"", headers=headers))
    with pytest.raises(RuntimeError, match="NATS RPC"):
        call(client)
    assert nc.request.await_count == 1


def test_empty_successful_protobuf_remains_valid(client):
    connection(client, return_value=SimpleNamespace(data=b"", headers=None))
    assert call(client) == keyvalue_pb2.GetResponse()


def test_request_limit_includes_auth_headers(client):
    nc = connection(client)
    nc.max_payload = 100
    with pytest.raises(RuntimeError, match="PAYLOAD_TOO_LARGE"):
        call(client)
    nc.request.assert_not_awaited()


def test_client_preserves_reconnecting_connection(client, monkeypatch):
    nc = connection(client)
    nc.is_connected = False
    connect = AsyncMock()
    monkeypatch.setattr("nats.connect", connect)
    assert asyncio.run(client._ensure_connection_async()) is nc
    connect.assert_not_awaited()


@pytest.fixture(params=ADAPTERS, ids=lambda pair: pair[0])
def primary(request):
    cls = adapter_class(*request.param, primary=True)
    instance = cls.__new__(cls)
    from naas_abi_core.engine.nats_dispatch import DomainRPCDispatcher

    instance._jwt_secret = SECRET
    instance._dispatch = DomainRPCDispatcher(request.param[0])
    yield instance
    instance._dispatch.close()


def response_class(primary):
    if type(primary).__name__ == "DatasetPrimaryAdapterNATS":
        return dataset_pb2.DescribeResponse
    return keyvalue_pb2.GetResponse


def error_of(response):
    if isinstance(response, dataset_pb2.DescribeResponse):
        return response.error.error
    return response.error


def test_primary_returns_non_retryable_error_for_oversized_reply(primary):
    replies = []
    response_cls = response_class(primary)

    async def respond(data):
        if len(data) > 512:
            raise MaxPayloadError()
        replies.append(response_cls.FromString(data))

    request = SimpleNamespace(
        data=keyvalue_pb2.GetRequest(key="k").SerializeToString(),
        headers={"Nats-Auth-Token": issue_service_token("test", SECRET)},
        subject="abi.test",
        respond=respond,
    )
    if response_cls is dataset_pb2.DescribeResponse:
        oversized_response = dataset_pb2.DescribeResponse(
            error=dataset_pb2.DatasetError(
                error=common_pb2.CallError(code="INTERNAL", message="x" * 1024)
            )
        )
    else:
        oversized_response = keyvalue_pb2.GetResponse(value=b"x" * 1024)
    operation = Mock(return_value=oversized_response)
    asyncio.run(
        primary._handle(request, keyvalue_pb2.GetRequest, response_cls, operation)
    )
    operation.assert_called_once()
    assert len(replies) == 1
    assert error_of(replies[0]).code == "PAYLOAD_TOO_LARGE"
    assert not error_of(replies[0]).retryable


def test_primary_rejects_malformed_protobuf_before_dispatch(primary):
    response_cls = response_class(primary)
    request = SimpleNamespace(
        data=b"\xff",
        headers={"Nats-Auth-Token": issue_service_token("test", SECRET)},
        subject="abi.test",
        respond=AsyncMock(),
    )
    operation = Mock()
    asyncio.run(
        primary._handle(request, keyvalue_pb2.GetRequest, response_cls, operation)
    )
    operation.assert_not_called()
    response = response_cls.FromString(request.respond.call_args.args[0])
    assert error_of(response).code == "INVALID_ARGUMENT"
    assert not error_of(response).retryable


@pytest.mark.parametrize("nested", [False, True])
def test_client_raises_typed_payload_error_for_both_error_shapes(client, nested):
    from naas_abi_core.engine.nats_rpc import NatsRPCPayloadTooLargeError

    error = common_pb2.CallError(code="PAYLOAD_TOO_LARGE", message="too big")
    response = (
        dataset_pb2.DescribeResponse(error=dataset_pb2.DatasetError(error=error))
        if nested
        else keyvalue_pb2.GetResponse(error=error)
    )
    connection(
        client,
        return_value=SimpleNamespace(data=response.SerializeToString(), headers=None),
    )
    with pytest.raises(NatsRPCPayloadTooLargeError):
        client._call("abi.test", keyvalue_pb2.GetRequest(key="k"), type(response))


def test_timeout_cancels_local_wait_without_replaying(client):
    from threading import Event

    cancelled = Event()

    async def slow_request(*args, **kwargs):
        try:
            await asyncio.Future()
        finally:
            cancelled.set()

    client._timeout_seconds = 0.05
    nc = connection(client, side_effect=slow_request)
    with pytest.raises(TimeoutError):
        call(client)
    assert cancelled.wait(1)
    assert nc.request.await_count == 1


def test_concurrent_requests_share_connection_without_serializing(client):
    from concurrent.futures import ThreadPoolExecutor

    entered = 0
    all_entered = None

    async def request(*args, **kwargs):
        nonlocal entered, all_entered
        if all_entered is None:
            all_entered = asyncio.Event()
        entered += 1
        if entered == 4:
            all_entered.set()
        await asyncio.wait_for(all_entered.wait(), 1)
        return SimpleNamespace(data=b"", headers={})

    nc = connection(client, side_effect=request)
    with ThreadPoolExecutor(max_workers=4) as pool:
        assert len(list(pool.map(lambda _: call(client), range(4)))) == 4
    assert nc.request.await_count == 4


def test_simultaneous_first_requests_share_completed_connection(monkeypatch):
    from naas_abi_core.engine.nats_rpc import NatsRPCClient

    nc = SimpleNamespace(is_closed=False, close=AsyncMock())

    async def connect(*args, **kwargs):
        await asyncio.sleep(0.01)

    nc.connect = AsyncMock(side_effect=connect)
    factory = Mock(return_value=nc)
    monkeypatch.setattr("naas_abi_core.engine.nats_rpc.NATSClient", factory)
    client = NatsRPCClient("nats://unused:4222", SECRET, "test")

    async def scenario():
        connections = await asyncio.gather(
            *(client._ensure_connection_async() for _ in range(8))
        )
        assert all(c is nc for c in connections)
        nc.connect.assert_awaited_once()
        factory.assert_called_once()

    asyncio.run(scenario())
