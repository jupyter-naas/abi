import asyncio
from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest

pytest.importorskip("langchain_core")
from langchain_core.messages import AIMessage, HumanMessage
from naas_abi_proto.model_registry.v1 import model_registry_pb2 as pb

from naas_abi_sdk.discovery import ModelDescriptor, ModuleInstance
from naas_abi_sdk.model_codec import decode_message, encode_message
from naas_abi_sdk.model_host import ModelHost
from naas_abi_sdk.transport import RPCError


class Writer:
    def __init__(self):
        self.messages = None

    async def invoke(self, messages):
        self.messages = messages
        return "hello"


class ToolCaller:
    async def invoke(self, messages, *, tools, tool_options=None):
        self.tools = tools
        self.tool_options = tool_options
        return AIMessage(
            content="",
            tool_calls=[
                {
                    "name": "get_time",
                    "args": {"timezone": "UTC"},
                    "id": "call_1",
                    "type": "tool_call",
                }
            ],
        )


def test_module_model_returns_text_and_tool_calls():
    async def scenario():
        writer = Writer()
        host = ModelHost(SimpleNamespace(), {"writer": writer})
        message = await host._invoke(
            "writer",
            pb.ChatRequest(
                ref=pb.ModelRef(canonical_id="writer", kind="chat"),
                messages=[encode_message(HumanMessage("hi"))],
            ),
        )
        assert writer.messages[0].content == "hi"
        assert message.type == "ai"
        with pytest.raises(RPCError, match="does not accept tools"):
            await host._invoke(
                "writer",
                pb.ChatRequest(
                    ref=pb.ModelRef(canonical_id="writer", kind="chat"),
                    messages=[encode_message(HumanMessage("hi"))],
                    tools_json=[b"{}"],
                ),
            )
        caller = ToolCaller()
        host = ModelHost(SimpleNamespace(), {"writer": caller})
        called = await host._invoke(
            "writer",
            pb.ChatRequest(
                ref=pb.ModelRef(canonical_id="writer", kind="chat"),
                messages=[encode_message(HumanMessage("hi"))],
                tools_json=[b'{"name":"get_time"}'],
                tool_options_json=b'{"tool_choice":"auto"}',
            ),
        )
        assert caller.tools == [{"name": "get_time"}]
        assert caller.tool_options == {"tool_choice": "auto"}
        assert decode_message(called).tool_calls[0]["name"] == "get_time"
        host.closing = True
        with pytest.raises(RPCError, match="draining"):
            await host._invoke(
                "writer",
                pb.ChatRequest(
                    ref=pb.ModelRef(canonical_id="writer", kind="chat"),
                    messages=[encode_message(HumanMessage("hi"))],
                ),
            )

    asyncio.run(scenario())


def test_module_proxy_invokes_the_serving_instance():
    async def scenario():
        from naas_abi_sdk.discovery import ModuleProxy
        from naas_abi_sdk.model_codec import decode_message

        descriptor = ModelDescriptor("writer")
        instance = ModuleInstance(
            "acme.models",
            "instance-1",
            "0.0.0",
            1,
            "READY",
            0.0,
            (),
            models=(descriptor,),
        )
        response = pb.ChatResponse(message=encode_message(AIMessage("hello")))
        transport = SimpleNamespace(call=AsyncMock(return_value=response))
        proxy = ModuleProxy(
            SimpleNamespace(
                project="default",
                transport=transport,
                get_module=AsyncMock(return_value=(instance,)),
            ),
            "acme.models",
        )
        model = await proxy.get_chat_model("writer")
        result = await model.model.ainvoke("Explain this")
        assert result.content == "hello"
        subject, request = transport.call.await_args.args[:2]
        assert subject == "abi.mod.default.instance-1.model.writer.chat"
        assert decode_message(request.messages[0]).content == "Explain this"

    asyncio.run(scenario())


class Slow:
    """A module model whose chats wait until released."""

    def __init__(self):
        self.running = 0
        self.peak = 0
        self.release = asyncio.Event()

    async def invoke(self, messages):
        self.running += 1
        self.peak = max(self.peak, self.running)
        try:
            await self.release.wait()
        finally:
            self.running -= 1
        return "hello"


def _serving(model):
    """A started host for ``model`` and the callback of its model subject."""
    callbacks = []

    async def subscribe(subject, cb=None, **kwargs):
        callbacks.append(cb)
        return AsyncMock()

    nc = SimpleNamespace(subscribe=subscribe, flush=AsyncMock())
    session = SimpleNamespace(
        instance_id="i-1",
        lease_token="lease",
        client=SimpleNamespace(
            project="default",
            transport=SimpleNamespace(connect=AsyncMock(return_value=nc)),
            _call=AsyncMock(),  # discovery's authorize_model
        ),
    )
    return ModelHost(session, {"writer": model}), callbacks


def _chat(replies):
    async def publish(subject, data, headers=None):
        replies.append(pb.ChatResponse.FromString(data))

    return SimpleNamespace(
        subject="abi.model.default.i-1.writer",
        data=pb.ChatRequest(
            ref=pb.ModelRef(canonical_id="writer", kind="chat"),
            messages=[encode_message(HumanMessage("hi"))],
        ).SerializeToString(),
        headers={"Nats-Auth-Token": "token"},
        reply="_INBOX.1",
        _client=SimpleNamespace(max_payload=1 << 20, publish=publish),
    )


async def _until(predicate):
    for _ in range(200):
        if predicate():
            return
        await asyncio.sleep(0.01)
    raise AssertionError("timed out")


def test_a_module_model_answers_its_chats_side_by_side():
    async def scenario():
        model, replies = Slow(), []
        host, callbacks = _serving(model)
        await host.start()
        (receive,) = callbacks
        for _ in range(3):
            # Returns at once: one chat at a time would block here.
            await asyncio.wait_for(receive(_chat(replies)), timeout=1)
        await _until(lambda: model.running == 3)
        model.release.set()
        await _until(lambda: len(replies) == 3)
        await host.close()
        return model, replies

    model, replies = asyncio.run(scenario())

    assert model.peak == 3
    assert [reply.message.type for reply in replies] == ["ai"] * 3


def test_closing_a_model_host_cancels_the_chats_still_running():
    async def scenario():
        model = Slow()
        host, callbacks = _serving(model)
        await host.start()
        await asyncio.wait_for(callbacks[0](_chat([])), timeout=1)
        await _until(lambda: model.running == 1)
        await host.close()
        return model

    assert asyncio.run(scenario()).running == 0
