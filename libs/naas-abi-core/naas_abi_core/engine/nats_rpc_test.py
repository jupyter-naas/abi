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
    reply_headers = []
    response_cls = response_class(primary)

    async def respond(data, headers=None):  # nats.micro Request.respond
        if len(data) > 512:
            raise MaxPayloadError()
        replies.append(response_cls.FromString(data))
        reply_headers.append(headers)

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
    assert reply_headers == [{"Abi-Error-Code": "PAYLOAD_TOO_LARGE"}]


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


# --- overflow: payloads above the broker limit (docs/adr/20261003_nats-rpc-overflow.md)

OWNER = "b" * 32


class FakeOverflowHost:
    """Stands in for the process's OverflowHost on the primary side."""

    def __init__(self, upload=b"", error=None):
        self.upload, self.error = upload, error
        self.parked = []

    def accepts(self, size):
        return True

    async def park(self, headers, data):
        self.parked.append(data)
        return f"{OWNER}:parked"

    async def fetch(self, transfer_id, headers):
        if self.error is not None:
            raise self.error
        return self.upload


@pytest.fixture
def overflow_host():
    from naas_abi_core.engine import nats_overflow

    host = FakeOverflowHost()
    nats_overflow.install(host)
    yield host
    nats_overflow.uninstall(host)


def primary_request(data, **headers):
    return SimpleNamespace(
        data=data,
        headers={"Nats-Auth-Token": issue_service_token("test", SECRET), **headers},
        subject="abi.test",
        respond=AsyncMock(),
        # The connection it arrived on, as nats.micro's Request carries it.
        _msg=SimpleNamespace(_client=SimpleNamespace(max_payload=8 * 1024 * 1024)),
    )


def test_primary_parks_an_oversized_reply_for_a_client_that_accepts_it(
    primary, overflow_host
):
    response_cls = response_class(primary)
    reply = response_cls()
    if response_cls is keyvalue_pb2.GetResponse:
        reply.value = b"x" * (9 * 1024 * 1024)
    else:
        reply.error.error.message = "x" * (9 * 1024 * 1024)
    request = primary_request(
        keyvalue_pb2.GetRequest(key="k").SerializeToString(), **{"Abi-Overflow": "1"}
    )

    asyncio.run(
        primary._handle(
            request, keyvalue_pb2.GetRequest, response_cls, Mock(return_value=reply)
        )
    )

    assert overflow_host.parked == [reply.SerializeToString()]
    request.respond.assert_awaited_once_with(
        b"",
        headers={
            "Abi-Overflow-Reply": f"{OWNER}:parked",
            "Abi-Overflow-Size": str(len(reply.SerializeToString())),
        },
    )


def test_primary_keeps_payload_too_large_for_a_client_without_overflow(
    primary, overflow_host
):
    response_cls = response_class(primary)
    reply = keyvalue_pb2.GetResponse(value=b"x" * (9 * 1024 * 1024))
    request = primary_request(keyvalue_pb2.GetRequest(key="k").SerializeToString())

    asyncio.run(
        primary._handle(
            request, keyvalue_pb2.GetRequest, response_cls, Mock(return_value=reply)
        )
    )

    assert overflow_host.parked == []
    response = response_cls.FromString(request.respond.call_args.args[0])
    assert error_of(response).code == "PAYLOAD_TOO_LARGE"


def test_primary_reads_an_uploaded_request_before_dispatch(primary, overflow_host):
    overflow_host.upload = keyvalue_pb2.GetRequest(key="uploaded").SerializeToString()
    response_cls = response_class(primary)
    operation = Mock(return_value=response_cls())
    request = primary_request(b"", **{"Abi-Overflow-Request": f"{OWNER}:up"})

    asyncio.run(
        primary._handle(request, keyvalue_pb2.GetRequest, response_cls, operation)
    )

    assert operation.call_args.args[0].key == "uploaded"


def test_primary_reports_an_upload_it_cannot_read(primary, overflow_host):
    from naas_abi_core.engine.nats_transfer import TransferError

    overflow_host.error = TransferError("NOT_FOUND", "Transfer expired or closed")
    response_cls = response_class(primary)
    operation = Mock(return_value=response_cls())
    request = primary_request(b"", **{"Abi-Overflow-Request": f"{OWNER}:gone"})

    asyncio.run(
        primary._handle(request, keyvalue_pb2.GetRequest, response_cls, operation)
    )

    operation.assert_not_called()
    response = response_cls.FromString(request.respond.call_args.args[0])
    assert error_of(response).code == "NOT_FOUND"
    assert not error_of(response).retryable


class OverflowOwner:
    """The broker's overflow subjects, owned by a host holding one parked reply."""

    def __init__(self, parked=b"", chunk=1024):
        from naas_abi_proto.transfer.v1 import transfer_pb2 as pb

        self.pb, self.parked, self.chunk = pb, parked, chunk
        self.uploads, self.closed, self.offset = {}, [], 0

    def reply(self, subject, payload):
        pb, operation = self.pb, subject.rsplit(".", 1)[1]
        if operation == "open":
            self.uploads[f"{OWNER}:up"] = bytearray()
            response = pb.OpenResponse(id=f"{OWNER}:up", chunk_bytes=self.chunk)
        elif operation == "write":
            request = pb.WriteRequest.FromString(payload)
            self.uploads[request.id].extend(request.data)
            response = pb.WriteResponse()
        elif operation == "read":
            request = pb.ReadRequest.FromString(payload)
            data = self.parked[self.offset : self.offset + self.chunk]
            self.offset += len(data)
            response = pb.ReadResponse(
                data=data, frame_end=True, done=not data, sequence=request.sequence
            )
        else:
            self.closed.append(pb.CloseRequest.FromString(payload).id)
            response = pb.CloseResponse()
        return SimpleNamespace(data=response.SerializeToString(), headers=None)


def test_client_downloads_an_overflowed_reply(client):
    value = bytes(range(256)) * 40
    parked = keyvalue_pb2.GetResponse(value=value).SerializeToString()
    owner = OverflowOwner(parked)
    service_headers = []

    async def request(subject, payload, timeout=None, headers=None):
        if subject.startswith("abi.rpc.overflow."):
            return owner.reply(subject, payload)
        service_headers.append(headers)
        return SimpleNamespace(
            data=b"",
            headers={
                "Abi-Overflow-Reply": f"{OWNER}:parked",
                "Abi-Overflow-Size": str(len(parked)),
            },
        )

    connection(client, side_effect=request)

    assert call(client).value == value
    assert owner.closed == [f"{OWNER}:parked"]
    assert service_headers[0]["Abi-Overflow"] == "1"


def test_client_uploads_a_request_above_the_broker_limit(client):
    owner = OverflowOwner()
    received = []

    async def request(subject, payload, timeout=None, headers=None):
        if subject.startswith("abi.rpc.overflow."):
            return owner.reply(subject, payload)
        received.append((payload, headers))
        return SimpleNamespace(data=b"", headers=None)

    nc = connection(client, side_effect=request)
    nc.max_payload = 4096

    client._call(
        "abi.test", keyvalue_pb2.GetRequest(key="k" * 10_000), keyvalue_pb2.GetResponse
    )

    ((payload, headers),) = received
    assert payload == b"" and headers["Abi-Overflow-Request"] == f"{OWNER}:up"
    uploaded = keyvalue_pb2.GetRequest.FromString(bytes(owner.uploads[f"{OWNER}:up"]))
    assert uploaded.key == "k" * 10_000
    assert owner.closed == [f"{OWNER}:up"]


def test_client_without_an_overflow_owner_keeps_payload_too_large(client):
    async def request(subject, payload, timeout=None, headers=None):
        if subject.startswith("abi.rpc.overflow."):
            raise NoRespondersError()
        raise AssertionError("the service must not be called")

    nc = connection(client, side_effect=request)
    nc.max_payload = 4096
    from naas_abi_core.engine.nats_rpc import NatsRPCPayloadTooLargeError

    with pytest.raises(NatsRPCPayloadTooLargeError):
        client._call(
            "abi.test",
            keyvalue_pb2.GetRequest(key="k" * 10_000),
            keyvalue_pb2.GetResponse,
        )


# --- the broker's max_payload is the only limit (no hard-coded 8 MiB)


def test_client_sends_up_to_the_brokers_limit_without_overflow(client):
    nc = connection(
        client,
        return_value=SimpleNamespace(
            data=keyvalue_pb2.GetResponse().SerializeToString(), headers=None
        ),
    )
    nc.max_payload = 16 * 1024 * 1024  # a broker configured above 8 MiB

    client._call(
        "abi.test",
        keyvalue_pb2.GetRequest(key="k" * (10 * 1024 * 1024)),
        keyvalue_pb2.GetResponse,
    )

    (subject, payload), _ = nc.request.call_args
    assert subject == "abi.test" and len(payload) > 10 * 1024 * 1024


def test_primary_counts_reply_headers_against_the_brokers_limit(primary):
    # NATS counts headers in the message size and closes the connection on a
    # violation; nats-py only checks the body. An error reply's body that fits
    # but whose Abi-Error-Code header does not must never be published as is.
    response_cls = response_class(primary)
    limit = 4096
    published = []

    async def respond(data, headers=None):
        block = "".join(f"{k}: {v}\r\n" for k, v in (headers or {}).items())
        size = len(data) + (len(f"NATS/1.0\r\n{block}\r\n") if headers else 0)
        assert size <= limit, "a message over the broker limit closes the connection"
        published.append(response_cls.FromString(data))

    request = SimpleNamespace(
        data=keyvalue_pb2.GetRequest(key="k").SerializeToString(),
        headers={"Nats-Auth-Token": issue_service_token("test", SECRET)},
        subject="abi.test",
        respond=respond,
        _msg=SimpleNamespace(_client=SimpleNamespace(max_payload=limit)),
    )
    reply = response_cls()
    error = error_of(reply)
    error.code, error.message = "INTERNAL", "x" * (limit - 40)
    assert len(reply.SerializeToString()) <= limit  # the body alone fits

    asyncio.run(
        primary._handle(
            request, keyvalue_pb2.GetRequest, response_cls, Mock(return_value=reply)
        )
    )

    assert [error_of(r).code for r in published] == ["PAYLOAD_TOO_LARGE"]
