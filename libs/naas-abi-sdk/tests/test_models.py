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
