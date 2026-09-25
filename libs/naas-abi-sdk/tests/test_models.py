import asyncio
from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest

pytest.importorskip("langchain_core")
from langchain_core.messages import AIMessage, AIMessageChunk, HumanMessage, ToolMessage
from naas_abi_proto.model_registry.v1 import model_registry_pb2 as pb

from naas_abi_sdk.model_codec import decode_message, encode_message
from naas_abi_sdk.models import ChatModelProxy, ModelConnection
from naas_abi_sdk.transport import RPCError


def test_message_roundtrip_preserves_tools_multimodal_and_usage():
    messages = [
        HumanMessage(
            content=[
                {
                    "type": "image_url",
                    "image_url": {"url": "data:image/png;base64,YQ=="},
                }
            ]
        ),
        AIMessage(
            content="",
            tool_calls=[
                {
                    "name": "weather",
                    "args": {"city": "Paris"},
                    "id": "call-1",
                    "type": "tool_call",
                }
            ],
            usage_metadata={"input_tokens": 2, "output_tokens": 3, "total_tokens": 5},
        ),
        ToolMessage(content="sunny", tool_call_id="call-1"),
        AIMessageChunk(
            content="",
            tool_call_chunks=[
                {"name": "weather", "args": '{"city":', "id": "call-1", "index": 0}
            ],
        ),
    ]
    for message in messages:
        assert decode_message(encode_message(message)) == message
    with pytest.raises(ValueError):
        decode_message(pb.ChatMessage(type="constructor", data_json=b"{}"))
    with pytest.raises(TypeError):
        encode_message(ToolMessage(content="x", tool_call_id="x", artifact=object()))


def test_proxy_tools_sync_bridge_stream_cleanup_and_no_retries(monkeypatch):
    async def frames(client, operation, request):
        if operation == "chat":
            yield (await client.chat(request)).SerializeToString()
        else:
            await client.stream_open(pb.StreamOpenRequest(chat=request))
            try:
                while True:
                    response = await client.stream_next(pb.StreamNextRequest())
                    if response.done:
                        break
                    yield response.chunk.SerializeToString()
            finally:
                await client.stream_close(pb.StreamCloseRequest())

    monkeypatch.setattr("naas_abi_sdk.models.model_frames", frames)

    async def scenario():
        client = SimpleNamespace(
            chat=AsyncMock(
                return_value=pb.ChatResponse(
                    message=encode_message(AIMessage(content="hello"))
                )
            ),
            stream_open=AsyncMock(
                return_value=pb.StreamOpenResponse(stream_id="stream")
            ),
            stream_next=AsyncMock(
                side_effect=[
                    pb.StreamNextResponse(
                        sequence=0, chunk=encode_message(AIMessageChunk(content="he"))
                    ),
                    pb.StreamNextResponse(sequence=1, done=True),
                ]
            ),
            stream_close=AsyncMock(return_value=pb.StreamCloseResponse()),
        )
        proxy = ChatModelProxy(
            connection=ModelConnection(client),
            ref=pb.ModelRef(canonical_id="demo", provider="test", kind="chat"),
            model_id="demo",
            provider="test",
        )
        tool = {
            "type": "function",
            "function": {
                "name": "weather",
                "description": "Weather",
                "parameters": {"type": "object", "properties": {}},
            },
        }
        bound = proxy.bind_tools([tool], tool_choice="auto")
        assert (await bound.ainvoke("hi")).content == "hello"
        request = client.chat.call_args.args[0]
        assert len(request.tools_json) == 1
        assert b"auto" in request.tool_options_json
        assert (await asyncio.to_thread(proxy.invoke, "sync")).content == "hello"
        with pytest.raises(RuntimeError, match="async model"):
            proxy.invoke("deadlock")
        chunks = [chunk async for chunk in proxy.astream("stream")]
        assert "".join(chunk.content for chunk in chunks) == "he"
        client.stream_close.assert_awaited_once()
        client.chat.reset_mock()
        client.chat.side_effect = RPCError("MODEL_ERROR", "failed")
        with pytest.raises(RPCError):
            await proxy.ainvoke("hi")
        client.chat.assert_awaited_once()

    asyncio.run(scenario())


def test_cross_loop_cancellation_waits_for_generator_cleanup(monkeypatch):
    import threading

    loop = asyncio.new_event_loop()
    thread = threading.Thread(target=loop.run_forever)
    thread.start()
    entered, cleaned = threading.Event(), threading.Event()

    async def frames(*args):
        try:
            entered.set()
            await asyncio.Event().wait()
            yield b"unused"
        finally:
            await asyncio.sleep(0.02)
            cleaned.set()

    monkeypatch.setattr("naas_abi_sdk.models.model_frames", frames)

    async def scenario():
        connection = ModelConnection(SimpleNamespace())
        connection.loop = loop

        async def consume():
            async for _ in connection.frames("stream", pb.ChatRequest()):
                pass

        task = asyncio.create_task(consume())
        assert await asyncio.to_thread(entered.wait, 1)
        task.cancel()
        with pytest.raises(asyncio.CancelledError):
            await asyncio.wait_for(task, 1)
        assert cleaned.is_set()

    try:
        asyncio.run(scenario())
    finally:
        loop.call_soon_threadsafe(loop.stop)
        thread.join(2)
        loop.close()


def test_model_iterator_can_be_closed_by_a_different_task(monkeypatch):
    closed = []

    async def frames(*args):
        try:
            yield b"first"
            yield b"second"
        finally:
            closed.append(True)

    monkeypatch.setattr("naas_abi_sdk.models.model_frames", frames)

    async def scenario():
        connection = ModelConnection(SimpleNamespace())
        iterator = connection.frames("stream", pb.ChatRequest())
        assert await iterator.__anext__() == b"first"
        await asyncio.wait_for(asyncio.create_task(iterator.aclose()), 1)
        assert closed == [True]

    asyncio.run(scenario())
