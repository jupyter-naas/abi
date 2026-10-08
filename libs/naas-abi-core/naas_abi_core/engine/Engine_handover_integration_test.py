"""Engines on a real broker: the serving engine's instance id, its sessions at
shutdown, and a client engine that opens nothing on its host.

See docs/adr/20261006_single-serving-engine.md.
"""

import asyncio
import os
import threading
import time
from collections.abc import Iterator
from contextlib import contextmanager
from pathlib import Path

import nats
import pytest
from naas_abi_core.engine.nats_auth import issue_service_token
from naas_abi_core.engine.nats_test_server import native_nats_server, nats_server_binary
from naas_abi_core.engine.nats_transfer import TransferError
from naas_abi_core.proto.object_storage.v1 import object_storage_pb2
from naas_abi_proto.transfer.v1 import transfer_pb2 as pb
from naas_abi_sdk.transfer import Transfer, transfer_subject
from nats.errors import NoRespondersError

pytestmark = pytest.mark.integration

SECRET = "engine-handover-test-secret-at-least-32-bytes"
OBJECTS = "abi.svc.object_storage.v1.transfer"
MODELS = "abi.svc.model_registry.v1"
# Every transfer host a serving engine starts, with an operation it accepts.
TRANSFER_HOSTS = [
    (OBJECTS, "get"),
    ("abi.svc.dataset.v1.transfer", "query"),
    ("abi.svc.triple_store.v1.transfer", "query"),
    ("abi.svc.vector_store.v1.transfer", "list_vectors"),
    ("abi.svc.activity_log.v1.transfer", "query"),
    ("abi.svc.event.v1.transfer", "query"),
    (f"{MODELS}.transfer", "chat"),
    ("abi.rpc.overflow", "request"),
]


@pytest.fixture
def broker(tmp_path):
    if nats_server_binary() is None:
        pytest.skip("nats-server is not installed")
    with native_nats_server(tmp_path, jetstream=True) as url:
        yield url


@pytest.fixture
def engine_dir(tmp_path, monkeypatch) -> Path:
    """The engine's working directory: its local backends live under it."""
    from naas_abi_core.engine.Engine import Engine

    work = tmp_path / "engine"
    work.mkdir()
    monkeypatch.chdir(work)
    # Built-in modules must not reach services from on_initialized here.
    monkeypatch.setattr(Engine, "on_initialized", lambda self: None)
    return work


def new_engine(url: str, **engine):
    from naas_abi_core.engine.Engine import Engine

    settings = ", ".join(f"{key}: {value}" for key, value in engine.items())
    return Engine(
        "api: {}\n"
        "global_config: {ai_mode: cloud, skip_ontology_loading: true}\n"
        "modules: []\n"
        "services: {secret: {secret_adapters: []}}\n"
        f"nats: {{nats_url: '{url}', jwt_secret: {SECRET}, engine: {{{settings}}}}}\n"
    )


def caller(nc):
    headers = {"Nats-Auth-Token": issue_service_token("caller", SECRET)}

    async def call(subject, request, response_type):
        request.context.timeout_ms = 5000
        reply = await nc.request(
            subject, request.SerializeToString(), headers=headers, timeout=5
        )
        response = response_type.FromString(reply.data)
        if response.HasField("error"):
            raise TransferError(response.error.code, response.error.message)
        return response

    return call


async def open_object(call, key: str) -> Transfer:
    metadata = object_storage_pb2.GetObjectRequest(prefix="handover", key=key)
    opened = await call(
        f"{OBJECTS}.open",
        pb.OpenRequest(operation="get", metadata=metadata.SerializeToString()),
        pb.OpenResponse,
    )
    transfer = Transfer(call, OBJECTS, opened.id, opened.chunk_bytes)
    await transfer.start()
    return transfer


async def close(call, prefix: str, transfer_id: str) -> None:
    await call(
        transfer_subject(prefix, "close", transfer_id),
        pb.CloseRequest(id=transfer_id),
        pb.CloseResponse,
    )


# --- one instance id -----------------------------------------------------------------------


def test_every_session_the_engine_owns_carries_the_id_that_holds_the_lease(
    broker, engine_dir
):
    from langchain_core.language_models.fake_chat_models import FakeListChatModel
    from langchain_core.messages import HumanMessage
    from naas_abi_core.engine.ownership.adapters.secondary.lease_jetstream import (
        JetStreamLease,
    )
    from naas_abi_core.models.Model import ChatModel
    from naas_abi_proto.model_registry.v1 import model_registry_pb2 as models_pb
    from naas_abi_sdk.model_codec import encode_message

    engine = new_engine(broker)
    engine.load()
    engine.services.model_registry.register(
        "fake-chat",
        ChatModel(
            model_id="fake",
            provider="openai",
            model=FakeListChatModel(responses=["hi"]),
        ),
    )

    async def owners() -> set[str]:
        nc = await nats.connect(broker)
        call = caller(nc)
        try:
            record = await (await JetStreamLease.open(nc)).read()
            assert record is not None
            found = {record.holder.instance_id}
            for prefix, operation in TRANSFER_HOSTS:
                opened = await call(
                    f"{prefix}.open",
                    pb.OpenRequest(operation=operation),
                    pb.OpenResponse,
                )
                found.add(opened.id.split(":")[0])
                await close(call, prefix, opened.id)
            chat = models_pb.ChatRequest(
                ref=models_pb.ModelRef(canonical_id="fake-chat", kind="chat"),
                messages=[encode_message(HumanMessage("hello"))],
            )
            stream = await call(
                f"{MODELS}.stream_open",
                models_pb.StreamOpenRequest(chat=chat),
                models_pb.StreamOpenResponse,
            )
            found.add(stream.stream_id.split(":")[0])
            await call(
                transfer_subject(MODELS, "stream_close", stream.stream_id),
                models_pb.StreamCloseRequest(stream_id=stream.stream_id),
                models_pb.StreamCloseResponse,
            )
            return found
        finally:
            await nc.close()

    try:
        assert asyncio.run(owners()) == {engine.instance_id}
    finally:
        engine.shutdown()


# --- sessions at shutdown ------------------------------------------------------------------


def test_a_transfer_in_progress_at_shutdown_completes(broker, engine_dir):
    engine = new_engine(broker, drain_seconds=30)
    engine.load()
    content = os.urandom(3 * 1024 * 1024)
    engine.services.object_storage.put_object("handover", "blob", content)
    stopping = threading.Thread(target=engine.shutdown)

    async def read_during_shutdown() -> bytes:
        nc = await nats.connect(broker)
        call = caller(nc)
        try:
            transfer = await open_object(call, "blob")
            fragments = transfer.fragments()
            data = bytearray((await anext(fragments))[0])

            stopping.start()
            # New transfers stop reaching this engine...
            deadline = time.monotonic() + 10
            while True:
                assert time.monotonic() < deadline, "the engine kept taking transfers"
                try:
                    probe = await open_object(call, "blob")
                except NoRespondersError:
                    break
                await close(call, OBJECTS, probe.id)
                await asyncio.sleep(0.05)
            # ...and it waits for the one in progress.
            await asyncio.sleep(0.3)
            assert stopping.is_alive()
            async for fragment, _ in fragments:
                data.extend(fragment)
            await close(call, OBJECTS, transfer.id)
            return bytes(data)
        finally:
            await nc.close()

    try:
        started = time.monotonic()
        assert asyncio.run(read_during_shutdown()) == content
        stopping.join(15)
        assert not stopping.is_alive()
        assert time.monotonic() - started < 15  # well before the drain deadline
    finally:
        engine.shutdown()


def test_a_stuck_transfer_is_closed_at_the_drain_deadline(broker, engine_dir):
    engine = new_engine(broker, drain_seconds=1)
    engine.load()
    engine.services.object_storage.put_object(
        "handover", "blob", os.urandom(3 * 1024 * 1024)
    )

    async def open_and_stall():
        nc = await nats.connect(broker)
        transfer = await open_object(caller(nc), "blob")
        await anext(transfer.fragments())
        return nc, transfer  # never read again, never closed

    loop = asyncio.new_event_loop()
    try:
        nc, transfer = loop.run_until_complete(open_and_stall())

        started = time.monotonic()
        engine.shutdown()
        elapsed = time.monotonic() - started

        assert 1 <= elapsed < 8
        with pytest.raises(NoRespondersError):
            loop.run_until_complete(
                caller(nc)(
                    transfer_subject(OBJECTS, "read", transfer.id),
                    pb.ReadRequest(id=transfer.id, sequence=1),
                    pb.ReadResponse,
                )
            )
        loop.run_until_complete(nc.close())
    finally:
        engine.shutdown()
        loop.close()


@contextmanager
def serving(url: str, primary) -> Iterator[None]:
    """``primary`` served from its own connection and loop: another engine's."""
    loop = asyncio.new_event_loop()
    thread = threading.Thread(target=loop.run_forever, daemon=True)
    thread.start()

    def run(coro):
        return asyncio.run_coroutine_threadsafe(coro, loop).result(10)

    nc = run(nats.connect(url))
    run(primary.start(nc))
    try:
        yield
    finally:
        run(primary.stop())
        run(nc.close())
        loop.call_soon_threadsafe(loop.stop)
        thread.join(5)


# --- one-shot calls at shutdown ------------------------------------------------------------


def test_a_one_shot_call_in_progress_at_shutdown_is_answered(
    broker, engine_dir, monkeypatch
):
    from concurrent.futures import ThreadPoolExecutor
    from unittest.mock import Mock

    from naas_abi_core.services.keyvalue.adapters.primary.keyvalue__primary_adapter__NATS import (
        KeyValuePrimaryAdapterNATS,
    )
    from naas_abi_core.services.keyvalue.adapters.secondary.KeyValueSecondaryAdapterNATSClient import (
        KeyValueSecondaryAdapterNATSClient,
    )
    from naas_abi_core.services.keyvalue.adapters.secondary.PythonAdapter import (
        PythonAdapter,
    )
    from naas_abi_core.services.keyvalue.KeyValueService import KeyValueService

    engine = new_engine(broker, drain_seconds=30)
    engine.load()
    engine.services.kv.set("slow", b"answered")
    handling, answer = threading.Event(), threading.Event()
    get = KeyValueService.get

    def slow_get(self, key):
        if key == "slow":
            handling.set()
            answer.wait(20)
        return get(self, key)

    monkeypatch.setattr(KeyValueService, "get", slow_get)
    # The next engine, which counts the calls it answers.
    store = PythonAdapter()
    store.set("slow", b"answered")
    next_engine = Mock(wraps=store)
    client = KeyValueSecondaryAdapterNATSClient(
        broker, SECRET, "caller", timeout_seconds=20
    )
    stopping = threading.Thread(target=engine.shutdown)
    try:
        with ThreadPoolExecutor(1) as calls:
            reading = calls.submit(client.get, "slow")
            assert handling.wait(10)
            with serving(broker, KeyValuePrimaryAdapterNATS(next_engine, SECRET)):
                started = time.monotonic()
                stopping.start()
                # New calls stop reaching this engine...
                deadline = time.monotonic() + 10
                while True:
                    assert time.monotonic() < deadline, "the engine kept taking calls"
                    before = next_engine.exists.call_count
                    for _ in range(5):
                        assert client.exists("slow")
                    if next_engine.exists.call_count - before == 5:
                        break
                # ...and it waits for the one in progress.
                time.sleep(0.3)
                assert stopping.is_alive()
                answer.set()
                assert reading.result(20) == b"answered"
                stopping.join(15)
                assert not stopping.is_alive()
                assert time.monotonic() - started < 15  # well before the deadline
    finally:
        answer.set()
        client.close()
        engine.shutdown()


# --- a client engine -----------------------------------------------------------------------


@contextmanager
def document_owner(url: str, path: Path) -> Iterator[None]:
    """The serving side of the one call a client engine makes while it loads:
    its agents' memory collections, in the serving engine's document service."""
    from naas_abi_core.services.document.adapters.primary.document__primary_adapter__NATS import (
        DocumentPrimaryAdapterNATS,
    )
    from naas_abi_core.services.document.adapters.secondary.DocumentSecondaryAdapterSQLite import (
        DocumentSecondaryAdapterSQLite,
    )
    from naas_abi_core.services.document.DocumentService import DocumentService

    primary = DocumentPrimaryAdapterNATS(
        DocumentService._for_engine(DocumentSecondaryAdapterSQLite(str(path))), SECRET
    )
    with serving(url, primary):
        yield


def test_a_client_engine_opens_no_local_backend(broker, engine_dir, tmp_path):
    from naas_abi_core.engine.context import get_default_agent_checkpointer
    from naas_abi_core.engine.nats_rpc import NatsRPCClient
    from nats.js.errors import BucketNotFoundError

    with document_owner(broker, tmp_path / "documents.sqlite"):
        engine = new_engine(broker, role="client")
        engine.load()
        try:
            assert list(engine_dir.rglob("*")) == []
            services = engine.services
            for service in (
                services.object_storage,
                services.document,
                services.dataset,
                services.kv,
                services.events,
                services.triple_store,
                services.vector_store,
            ):
                assert isinstance(service.adapter, NatsRPCClient)
            assert isinstance(
                get_default_agent_checkpointer().documents.adapter, NatsRPCClient
            )

            async def lease_bucket():
                nc = await nats.connect(broker)
                try:
                    await nc.jetstream().key_value("ABI_ENGINE")
                finally:
                    await nc.close()

            with pytest.raises(BucketNotFoundError):  # it never touched the lease
                asyncio.run(lease_bucket())
        finally:
            engine.shutdown()
    assert list(engine_dir.rglob("*")) == []
