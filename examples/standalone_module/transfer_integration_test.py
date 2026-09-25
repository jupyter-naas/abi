"""Payloads larger than the broker limit, with slow producers and bounded reads."""

import asyncio
import io
from contextlib import contextmanager

import nats
import pytest
from langchain_core.language_models.fake_chat_models import FakeListChatModel
from langchain_core.messages import AIMessage, AIMessageChunk, HumanMessage
from langchain_core.outputs import ChatGeneration, ChatGenerationChunk, ChatResult
from naas_abi_core.engine.nats_auth import issue_service_token
from naas_abi_core.engine.nats_rpc_integration_test import SECRET, broker  # noqa: F401
from naas_abi_core.models.Model import ChatModel
from naas_abi_core.services.model_registry.adapters.primary.model_registry_nats import (
    ModelRegistryNATS,
)
from naas_abi_core.services.model_registry.ModelRegistryService import (
    ModelRegistryService,
)
from naas_abi_core.services.object_storage.adapters.primary.object_storage__primary_adapter__NATS import (
    ObjectStoragePrimaryAdapterNATS,
)
from naas_abi_core.services.object_storage.adapters.secondary.ObjectStorageSecondaryAdapterFS import (
    ObjectStorageSecondaryAdapterFS,
)
from naas_abi_core.services.object_storage.adapters.secondary.ObjectStorageSecondaryAdapterNATSClient import (
    ObjectStorageSecondaryAdapterNATSClient,
)
from naas_abi_proto.transfer.v1 import transfer_pb2 as pb
from naas_abi_sdk import ABIClient
from naas_abi_sdk.services.model_registry import ModelRegistryService as ModelFacade
from naas_abi_sdk.services.object_storage import ObjectStorageService as ObjectFacade
from naas_abi_sdk.transfer import open_transfer
from naas_abi_sdk.transport import RPCError

pytestmark = [
    pytest.mark.integration,
    pytest.mark.parametrize("broker", [32 * 1024], indirect=True),
]


class BoundedFS(ObjectStorageSecondaryAdapterFS):
    reads: list[int] = []

    def get_object(self, prefix, key):
        raise AssertionError("Backend GET must use the streaming port")

    @contextmanager
    def get_object_stream(self, prefix, key):
        with super().get_object_stream(prefix, key) as stream:

            class Reader:
                def read(inner, size=-1):
                    assert 0 < size <= 64 * 1024
                    self.reads.append(size)
                    return stream.read(size)

            yield Reader()


class BoundedInput(io.BytesIO):
    def read(self, size=-1):
        assert 0 < size <= 64 * 1024
        return super().read(size)


def test_large_objects_stream_through_small_broker(broker, tmp_path):  # noqa: F811
    async def scenario():
        owner = BoundedFS(str(tmp_path))
        nc = await nats.connect(broker[0])
        primary = ObjectStoragePrimaryAdapterNATS(
            owner, SECRET, transfer_options={"idle_seconds": 0.15}
        )
        await primary.start(nc)
        content = bytes(range(256)) * 8192
        sync_client = ObjectStorageSecondaryAdapterNATSClient(broker[0], SECRET, "sync")
        try:
            async with ABIClient(
                broker[0], issue_service_token("sdk", SECRET)
            ) as client:
                storage = ObjectFacade(client.object_storage)
                await storage.put_object_stream("files", "large", BoundedInput(content))
                async with storage.get_object_stream("files", "large") as stream:
                    assert await stream.read(7) == content[:7]
                    received = bytearray(content[:7])
                    async for chunk in stream:
                        received.extend(chunk)
                assert bytes(received) == content
                assert await storage.get_object("files", "large") == content
                assert (
                    await asyncio.to_thread(sync_client.get_object, "files", "large")
                    == content
                )
                await asyncio.to_thread(
                    sync_client.put_object_stream,
                    "files",
                    "sync",
                    BoundedInput(content),
                )
                assert await storage.get_object("files", "sync") == content
                async with storage.get_object_stream("files", "large") as stream:
                    assert await stream.read(1) == content[:1]
                assert not primary._transfer.sessions
                assert owner.reads
                # An abandoned upload never commits and is removed by idle expiry.
                prefix = "abi.svc.object_storage.v1.transfer"
                opened = await client._transport.call(
                    f"{prefix}.open", pb.OpenRequest(operation="put"), pb.OpenResponse
                )
                async with ABIClient(
                    broker[0], issue_service_token("other", SECRET)
                ) as other:
                    with pytest.raises(RPCError, match="PERMISSION_DENIED"):
                        await other._transport.call(
                            f"{prefix}.close",
                            pb.CloseRequest(id=opened.id),
                            pb.CloseResponse,
                        )
                await asyncio.sleep(0.4)
                assert not primary._transfer.sessions
        finally:
            await asyncio.to_thread(sync_client.close)
            await primary.stop()
            await nc.close()

    asyncio.run(scenario())


def test_large_history_results_and_slow_generation(broker):  # noqa: F811
    async def scenario():
        text = "history-" * (128 * 1024)
        result = "answer-" * (128 * 1024)

        class SlowLargeModel(FakeListChatModel):
            async def _agenerate(self, messages, **kwargs):
                assert messages[-1].content == text
                await asyncio.sleep(0.3)
                return ChatResult(
                    generations=[ChatGeneration(message=AIMessage(content=result))]
                )

            async def _astream(self, messages, **kwargs):
                assert messages[-1].content == text
                await asyncio.sleep(0.3)
                yield ChatGenerationChunk(message=AIMessageChunk(content=result))
                await asyncio.sleep(0.3)
                yield ChatGenerationChunk(
                    message=AIMessageChunk(
                        content="end",
                        tool_call_chunks=[
                            {
                                "name": "large_tool",
                                "args": '{"value":"' + result + '"}',
                                "id": "call-large",
                                "index": 0,
                            }
                        ],
                    )
                )

        registry = ModelRegistryService()
        registry.register(
            "large",
            ChatModel(
                model_id="large",
                provider="test",
                model=SlowLargeModel(responses=["unused"]),
            ),
        )
        nc = await nats.connect(broker[0])
        primary = ModelRegistryNATS(registry, SECRET)
        await primary.start(nc)
        try:
            # Total generation and first-token waits exceed every per-RPC timeout.
            async with ABIClient(
                broker[0], issue_service_token("sdk", SECRET), timeout=0.15
            ) as client:
                model = (
                    await ModelFacade(client.model_registry).get_chat_model("large")
                ).model
                assert (
                    await model.ainvoke(
                        [HumanMessage(content="old")] * 1024
                        + [HumanMessage(content=text)]
                    )
                ).content == result
                chunks = [chunk async for chunk in model.astream(text)]
                assert "".join(chunk.content for chunk in chunks) == result + "end"
                assert chunks[-1].tool_calls[0]["args"] == {"value": result}
                assert not primary.transfer.sessions
                # Strict sequence checking: no replay of an uncertain upload.
                async with open_transfer(
                    client._transport, "abi.svc.model_registry.v1.transfer", "chat"
                ) as transfer:
                    await transfer.write(b"x")
                    with pytest.raises(RPCError, match="CONFLICT"):
                        await client._transport.call(
                            f"{transfer.prefix}.write",
                            pb.WriteRequest(id=transfer.id, sequence=0, data=b"x"),
                            pb.WriteResponse,
                        )
        finally:
            await primary.stop()
            await nc.close()

    asyncio.run(scenario())


def test_transfer_limits_reject_before_backend_mutation(broker, tmp_path):  # noqa: F811
    async def scenario():
        owner = ObjectStorageSecondaryAdapterFS(str(tmp_path))
        owner.put_object("files", "existing", b"original")
        nc = await nats.connect(broker[0])
        primary = ObjectStoragePrimaryAdapterNATS(
            owner, SECRET, transfer_options={"max_sessions": 1, "max_upload_bytes": 4}
        )
        await primary.start(nc)
        try:
            async with ABIClient(
                broker[0], issue_service_token("sdk", SECRET)
            ) as client:
                storage = ObjectFacade(client.object_storage)
                with pytest.raises(RPCError, match="PAYLOAD_TOO_LARGE"):
                    await storage.put_object("files", "existing", b"too large")
                with pytest.raises(RPCError, match="PAYLOAD_TOO_LARGE"):
                    await storage.put_object_stream(
                        "files", "existing", io.BytesIO(b"too large")
                    )
                assert owner.get_object("files", "existing") == b"original"
                assert not primary._transfer.sessions
                prefix = "abi.svc.object_storage.v1.transfer"
                async with open_transfer(client._transport, prefix, "get"):
                    with pytest.raises(RPCError, match="RESOURCE_EXHAUSTED"):
                        async with open_transfer(client._transport, prefix, "get"):
                            pytest.fail("Capacity limit was not enforced")
                assert not primary._transfer.sessions
        finally:
            await primary.stop()
            await nc.close()

    asyncio.run(scenario())


def test_two_engine_owners_execute_once_and_route_transfer_sessions(broker, tmp_path):  # noqa: F811
    async def scenario():
        calls = []

        class CountingModel(FakeListChatModel):
            async def _agenerate(self, messages, **kwargs):
                calls.append("invoke")
                return ChatResult(
                    generations=[ChatGeneration(message=AIMessage(content="answer"))]
                )

            async def _astream(self, messages, **kwargs):
                calls.append("stream")
                await asyncio.sleep(0.05)
                yield ChatGenerationChunk(message=AIMessageChunk(content="answer"))

        nc = await nats.connect(broker[0])
        registry = ModelRegistryService()
        registry.register(
            "count",
            ChatModel(
                model_id="count",
                provider="test",
                model=CountingModel(responses=["unused"]),
            ),
        )
        models = [ModelRegistryNATS(registry, SECRET) for _ in range(2)]
        storage = [
            ObjectStoragePrimaryAdapterNATS(
                ObjectStorageSecondaryAdapterFS(str(tmp_path)), SECRET
            )
            for _ in range(2)
        ]
        try:
            for primary in models + storage:
                await primary.start(nc)
            async with ABIClient(
                broker[0], issue_service_token("two-owners", SECRET)
            ) as client:
                proxy = (
                    await ModelFacade(client.model_registry).get_chat_model("count")
                ).model
                assert (await proxy.ainvoke("hi")).content == "answer"
                assert (
                    "".join([c.content async for c in proxy.astream("hi")]) == "answer"
                )
                objects = ObjectFacade(client.object_storage)
                value = b"many packets" * 65536
                for _ in range(4):
                    await objects.put_object("files", "shared", value)
                    assert await objects.get_object("files", "shared") == value
                from naas_abi_proto.model_registry.v1 import (
                    model_registry_pb2 as model_pb,
                )
                from naas_abi_sdk.model_codec import encode_message

                subjects = []

                async def observe(msg):
                    subjects.append(msg.subject)

                subscription = await nc.subscribe(
                    "abi.svc.model_registry.v1.>", cb=observe
                )
                await nc.flush()
                opened = await client.model_registry.stream_open(
                    model_pb.StreamOpenRequest(
                        chat=model_pb.ChatRequest(
                            ref=model_pb.ModelRef(
                                canonical_id="count", provider="test", kind="chat"
                            ),
                            messages=[encode_message(HumanMessage(content="hi"))],
                        ),
                    )
                )
                response = await client.model_registry.stream_next(
                    model_pb.StreamNextRequest(stream_id=opened.stream_id)
                )
                assert response.HasField("chunk")
                await client.model_registry.stream_close(
                    model_pb.StreamCloseRequest(stream_id=opened.stream_id)
                )
                await nc.flush()
                owner = opened.stream_id.split(":")[0]
                assert f"abi.svc.model_registry.v1.{owner}.stream_next" in subjects
                assert "abi.svc.model_registry.v1.stream_next" not in subjects
                assert f"abi.svc.model_registry.v1.{owner}.stream_close" in subjects
                await subscription.unsubscribe()
                assert calls == ["invoke", "stream", "stream"]
                assert all(not p.transfer.sessions for p in models)
                assert all(not p._transfer.sessions for p in storage)
        finally:
            for primary in models + storage:
                await primary.stop()
            await nc.close()

    asyncio.run(scenario())


def test_object_entry_errors_and_legacy_owner_fallback(broker, tmp_path):  # noqa: F811
    from naas_abi_core.services.object_storage.ObjectStoragePort import Exceptions
    from naas_abi_sdk.services.errors import ObjectNotFound

    async def scenario():
        owner = ObjectStorageSecondaryAdapterFS(str(tmp_path))
        nc = await nats.connect(broker[0])
        primary = ObjectStoragePrimaryAdapterNATS(owner, SECRET)
        await primary.start(nc)
        sync_client = ObjectStorageSecondaryAdapterNATSClient(broker[0], SECRET, "sync")

        def missing_sync():
            with (
                pytest.raises(Exceptions.ObjectNotFound),
                sync_client.get_object_stream("files", "missing"),
            ):
                pytest.fail("Missing object entered the context body")

        try:
            async with ABIClient(
                broker[0], issue_service_token("sdk", SECRET)
            ) as client:
                storage = ObjectFacade(client.object_storage)
                with pytest.raises(ObjectNotFound):
                    async with storage.get_object_stream("files", "missing"):
                        pytest.fail("Missing object entered the context body")
                await asyncio.to_thread(missing_sync)
                # Model an older owner that only publishes unary endpoints.
                await primary._transfer.stop()
                await nc.flush()
                await storage.put_object("files", "small", b"small")
                assert await storage.get_object("files", "small") == b"small"
                await storage.put_object_stream(
                    "files", "stream", io.BytesIO(b"stream")
                )
                assert (
                    await asyncio.to_thread(sync_client.get_object, "files", "stream")
                    == b"stream"
                )
                await asyncio.to_thread(
                    sync_client.put_object_stream, "files", "sync", io.BytesIO(b"sync")
                )
                assert await storage.get_object("files", "sync") == b"sync"
                with pytest.raises(ValueError, match="upgrade required"):
                    await storage.put_object_stream(
                        "files", "too-large", io.BytesIO(b"x" * 65536)
                    )
                assert "too-large" not in owner.list_objects("files")
        finally:
            await asyncio.to_thread(sync_client.close)
            await primary.stop()
            await nc.close()

    asyncio.run(scenario())
