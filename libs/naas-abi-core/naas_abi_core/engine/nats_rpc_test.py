"""Transport guarantees exercised through every concrete RPC adapter."""

import asyncio
import importlib
from types import SimpleNamespace
from unittest.mock import AsyncMock, Mock

import pytest
from naas_abi_core.engine.nats_test_tokens import TEST_TOKENS
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
SECRET = TEST_TOKENS.verifier
# The container a call is made in: request data, carried as is.
WS = "abi:nexus:organization/org-1/nexus:workspace/ws-1"


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
    with cls("nats://unused:4222", TEST_TOKENS.source("test")) as instance:
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


def test_a_transfer_open_rides_out_a_handover_but_its_session_calls_do_not(client):
    # The open goes to the serving engine's queue group, so "no responders"
    # (nobody subscribed during a handover) is safe to resend; the session's
    # own calls go to the engine that opened it.
    from naas_abi_proto.transfer.v1 import transfer_pb2
    from naas_abi_sdk.telemetry import TransferTrace

    prefix, owner = "abi.svc.test.v1.transfer", "c" * 32
    sent = []

    async def request(subject, payload, timeout=None, headers=None):
        sent.append(subject)
        if len(sent) == 1 or not subject.endswith(".open"):
            raise NoRespondersError()
        opened = transfer_pb2.OpenResponse(id=f"{owner}:1")
        return SimpleNamespace(data=opened.SerializeToString(), headers=None)

    connection(client, side_effect=request)

    opened = client._call(
        f"{prefix}.open",
        transfer_pb2.OpenRequest(),
        transfer_pb2.OpenResponse,
        transfer=TransferTrace(),
    )
    assert opened.id == f"{owner}:1"
    assert sent == [f"{prefix}.open", f"{prefix}.open"]

    with pytest.raises(NoRespondersError):
        client._call(
            f"{prefix}.{owner}.read",
            transfer_pb2.ReadRequest(id=opened.id),
            transfer_pb2.ReadResponse,
            transfer=TransferTrace(),
        )
    assert sent[2:] == [f"{prefix}.{owner}.read"]


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

    instance._verifier = SECRET
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
        headers={"Nats-Auth-Token": TEST_TOKENS.token("test")},
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
        headers={"Nats-Auth-Token": TEST_TOKENS.token("test")},
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


def test_a_call_deadline_replaces_the_client_default_for_that_call(client):
    async def slow_request(*args, **kwargs):
        await asyncio.sleep(0.2)
        return SimpleNamespace(data=b"", headers={})

    client._timeout_seconds = 0.05
    nc = connection(client, side_effect=slow_request)

    response = client._call(
        "abi.test",
        keyvalue_pb2.GetRequest(key="k"),
        keyvalue_pb2.GetResponse,
        timeout_seconds=2.0,
    )

    assert response == keyvalue_pb2.GetResponse()
    assert nc.request.await_args.kwargs["timeout"] == 2.0
    with pytest.raises(TimeoutError):  # the next call keeps the default
        call(client)


def test_the_call_context_carries_the_calls_deadline(client):
    client._timeout_seconds = 3.0

    assert client._context().timeout_ms == 3000
    assert client._context(timeout_seconds=7200.0).timeout_ms == 7_200_000


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
    client = NatsRPCClient("nats://unused:4222", TEST_TOKENS.source("test"))

    async def scenario():
        connections = await asyncio.gather(
            *(client._ensure_connection_async() for _ in range(8))
        )
        assert all(c is nc for c in connections)
        nc.connect.assert_awaited_once()
        factory.assert_called_once()

    asyncio.run(scenario())


# --- overflow: payloads above the broker limit

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
        headers={"Nats-Auth-Token": TEST_TOKENS.token("test"), **headers},
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
        headers={"Nats-Auth-Token": TEST_TOKENS.token("test")},
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


def test_uploads_are_regrouped_into_negotiated_chunks_lazily():
    from naas_abi_core.engine.nats_rpc import upload_chunks

    pieces = (b"x" * n for n in (3, 5, 0, 9, 1))  # 18 bytes

    assert [len(chunk) for chunk in upload_chunks(pieces, 4)] == [4, 4, 4, 4, 2]
    assert b"".join(upload_chunks([b"ab", b"cd"], 3)) == b"abcd"
    assert list(upload_chunks([], 4)) == []


def _api_client(identity: str = "api"):
    from naas_abi_core.engine.nats_rpc import NatsRPCClient

    client = NatsRPCClient("nats://unused:4222", TEST_TOKENS.source(identity))
    return client, connection(
        client,
        return_value=SimpleNamespace(
            data=keyvalue_pb2.GetResponse().SerializeToString(), headers=None
        ),
    )


@pytest.mark.parametrize("identity", ["api", "engine"])
def test_a_delegating_client_sends_a_delegation_naming_the_user(identity):
    from naas_abi_core.engine.call_context import (
        CallContext,
        service_account,
        use_call_context,
        user,
    )
    from naas_abi_core.engine.nats_identity import caller_context

    client, nc = _api_client(identity)
    caller = CallContext(
        principal=service_account("api"),
        on_behalf_of=user("usr-ada"),
        container=WS,
        trace_id="trace-1",
    )
    try:
        with use_call_context(caller):
            context = client._context()
            call(client)
    finally:
        client.close()
    headers = nc.request.call_args.kwargs["headers"]
    assert "Abi-On-Behalf-Of" not in headers
    served = caller_context(
        headers, TEST_TOKENS.verifier_for(("abi:nats", "abi:delegated:agent"))
    )
    assert served.principal.id == identity
    assert served.on_behalf_of is not None and served.on_behalf_of.id == "usr-ada"
    assert (context.trace_id, context.container) == ("trace-1", WS)
    assert not context.principal_id and not context.tenant_id


def test_another_client_calls_as_itself_and_never_carries_a_user():
    from naas_abi_core.engine.call_context import (
        CallContext,
        service_account,
        use_call_context,
        user,
    )
    from naas_abi_core.engine.nats_identity import caller_context

    client, nc = _api_client("dagster")
    try:
        with use_call_context(
            CallContext(principal=service_account("api"), on_behalf_of=user("u"))
        ):
            call(client)
    finally:
        client.close()
    headers = nc.request.call_args.kwargs["headers"]
    assert "Abi-On-Behalf-Of" not in headers
    served = caller_context(headers, TEST_TOKENS.verifier)
    assert served.principal.id == "dagster" and served.on_behalf_of is None


def test_a_delegation_that_fails_is_a_failed_call_not_the_clients_own_identity():
    from naas_abi_core.engine.call_context import (
        CallContext,
        service_account,
        use_call_context,
        user,
    )
    from naas_abi_core.engine.nats_auth import (
        InvalidServiceTokenError,
        RenewingTokenSource,
    )
    from naas_abi_core.engine.nats_rpc import NatsRPCClient

    def refuse(who, recipient, scope=None):
        raise InvalidServiceTokenError("suspended")

    client = NatsRPCClient(
        "nats://unused:4222",
        RenewingTokenSource("api", lambda: TEST_TOKENS.issue("api"), delegate=refuse),
    )
    nc = connection(client, return_value=SimpleNamespace(data=b"", headers=None))
    try:
        with (
            use_call_context(
                CallContext(principal=service_account("api"), on_behalf_of=user("u"))
            ),
            pytest.raises(InvalidServiceTokenError),
        ):
            call(client)
    finally:
        client.close()
    nc.request.assert_not_called()


def test_without_a_user_no_delegation_and_a_fresh_trace():
    from naas_abi_core.engine.nats_identity import caller_context

    client, nc = _api_client()
    try:
        call(client)
        context = client._context()
    finally:
        client.close()
    headers = nc.request.call_args.kwargs["headers"]
    assert "Abi-On-Behalf-Of" not in headers
    assert caller_context(headers, TEST_TOKENS.verifier).on_behalf_of is None
    assert context.trace_id and not context.container


def test_overflow_chunks_travel_as_the_call_they_belong_to(monkeypatch):
    from naas_abi_core.engine.call_context import (
        CallContext,
        service_account,
        use_call_context,
        user,
    )
    from naas_abi_core.engine.nats_identity import caller_context
    from naas_abi_core.engine.nats_rpc import NatsRPCClient
    from naas_abi_proto.transfer.v1 import transfer_pb2
    from naas_abi_sdk.telemetry import TransferTrace

    client = NatsRPCClient("nats://unused:4222", TEST_TOKENS.source("api"))
    sent = []

    async def request(subject, payload, headers, **kwargs):
        sent.append((transfer_pb2.CloseRequest.FromString(payload), headers))
        return SimpleNamespace(data=transfer_pb2.CloseResponse().SerializeToString())

    monkeypatch.setattr(client, "_do_request_async", request)
    caller = CallContext(principal=service_account("api"), on_behalf_of=user("u1"))
    call_request = keyvalue_pb2.SetRequest(
        context=common_pb2.CallContext(trace_id="trace-1", container=WS)
    )
    try:
        with use_call_context(caller):
            chunk = client._chunk_call(
                {"Nats-Auth-Token": client._current_token(client._served_user())},
                call_request,
                TransferTrace(None),
            )
        # Chunks run later, on the client's loop, outside the caller's context.
        for _ in range(2):
            asyncio.run(
                chunk(
                    "abi.overflow.close",
                    transfer_pb2.CloseRequest(),
                    transfer_pb2.CloseResponse,
                )
            )
    finally:
        client.close()
    for message, headers in sent:
        assert (message.context.trace_id, message.context.container) == (
            "trace-1",
            WS,
        )
        assert "Abi-On-Behalf-Of" not in headers
        served = caller_context(
            headers, TEST_TOKENS.verifier_for(("abi:nats", "abi:delegated:agent"))
        )
        assert served.on_behalf_of is not None and served.on_behalf_of.id == "u1"


def test_a_stream_keeps_the_user_it_was_opened_for(monkeypatch):
    """Frames read later, from another thread or after the caller's context
    ended, still carry the opener's user: the host refuses any other."""
    import threading

    from naas_abi_core.engine.call_context import (
        CallContext,
        service_account,
        use_call_context,
        user,
    )
    from naas_abi_core.engine.nats_rpc import NatsRPCClient
    from naas_abi_proto.transfer.v1 import transfer_pb2

    client = NatsRPCClient("nats://unused:4222", TEST_TOKENS.source("api"))
    users = []
    replies = {
        transfer_pb2.OpenResponse: transfer_pb2.OpenResponse(id="s", chunk_bytes=1024),
        transfer_pb2.StartResponse: transfer_pb2.StartResponse(),
        transfer_pb2.ReadResponse: transfer_pb2.ReadResponse(done=True),
        transfer_pb2.CloseResponse: transfer_pb2.CloseResponse(),
    }

    def fake_call(subject, request, response_cls, **kwargs):
        served = kwargs.get("user") or client._served_user()
        users.append(served.id if served is not None else None)
        return replies[response_cls]

    monkeypatch.setattr(client, "_call", fake_call)
    monkeypatch.setattr(
        client,
        "_run_coro",
        lambda coro, **_: (coro.close(), SimpleNamespace(max_payload=1 << 20))[1],
    )
    ada = CallContext(principal=service_account("api"), on_behalf_of=user("usr-ada"))
    try:
        with use_call_context(ada):
            stream = client._transfer_stream("abi.t", "get", b"", lambda e: None)
            frames = stream.__enter__()
        # Read and close on another thread, outside the opener's context.
        reader = threading.Thread(
            target=lambda: (list(frames), stream.__exit__(None, None, None))
        )
        reader.start()
        reader.join()
    finally:
        client.close()
    assert users and set(users) == {"usr-ada"}


def test_a_stream_keeps_the_scope_it_was_opened_with(monkeypatch):
    """A read-only key's stream is as narrow over NATS as in process: frames
    read from another thread, after the caller's context ended, still carry the
    opener's scope in their delegation."""
    import threading

    from naas_abi_core.engine.call_context import (
        CallContext,
        service_account,
        use_call_context,
        user,
    )
    from naas_abi_core.engine.nats_rpc import NatsRPCClient
    from naas_abi_proto.transfer.v1 import transfer_pb2

    read_only = (
        {"effect": "Allow", "actions": ["object_storage:Get*"], "resources": ["*"]},
    )
    seen = []

    class Source:
        identity = "api"

        def token(self):
            return "own"

        def token_for(self, who, recipient=None, scope=None):
            seen.append((who.id if who is not None else None, scope))
            return "t"

    client = NatsRPCClient("nats://unused:4222", Source())
    replies = {
        transfer_pb2.OpenResponse: transfer_pb2.OpenResponse(id="s", chunk_bytes=1024),
        transfer_pb2.StartResponse: transfer_pb2.StartResponse(),
        transfer_pb2.ReadResponse: transfer_pb2.ReadResponse(done=True),
        transfer_pb2.CloseResponse: transfer_pb2.CloseResponse(),
    }

    def fake_rpc(msg, response_cls, transfer):
        return replies[response_cls]

    monkeypatch.setattr(client, "_rpc_request", lambda *a, **k: None)
    monkeypatch.setattr(client, "_rpc_parse", fake_rpc)
    monkeypatch.setattr(
        client,
        "_run_coro",
        lambda coro, **_: (coro.close(), SimpleNamespace(max_payload=1 << 20))[1],
    )
    ada = CallContext(
        principal=service_account("api"),
        on_behalf_of=user("usr-ada"),
        scope=read_only,
    )
    try:
        with use_call_context(ada):
            stream = client._transfer_stream("abi.t", "get", b"", lambda e: None)
            frames = stream.__enter__()
        reader = threading.Thread(
            target=lambda: (list(frames), stream.__exit__(None, None, None))
        )
        reader.start()
        reader.join()
    finally:
        client.close()
    assert len(seen) >= 4  # open, start, read, close
    assert all(who == "usr-ada" and scope == read_only for who, scope in seen)
