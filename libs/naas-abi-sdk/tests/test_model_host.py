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
