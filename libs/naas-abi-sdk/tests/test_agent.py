import asyncio
from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest
from naas_abi_proto.agent.v1 import agent_pb2 as pb

from naas_abi_sdk.agent import AgentProxy, SubmissionUncertain
from naas_abi_sdk.discovery import AgentDescriptor


def proxy():
    descriptor = AgentDescriptor("Researcher", capabilities=("agent.invoke.v1",))
    transport = SimpleNamespace(call=AsyncMock())
    module = SimpleNamespace(
        client=SimpleNamespace(project="default", transport=transport),
        ready_instances=AsyncMock(
            return_value=[SimpleNamespace(instance_id="one", agents=(descriptor,))]
        ),
    )
    module.instances = module.ready_instances
    return AgentProxy(module, descriptor), transport


def test_proxy_invocation_hides_proto_and_duplicate_has_separate_thread():
    agent, transport = proxy()
    transport.call.side_effect = [
        pb.SubmitResponse(invocation=pb.Invocation(owner_instance_id="one")),
        pb.StatusResponse(invocation=pb.Invocation(status="SUCCEEDED", result="hello")),
        pb.StatusResponse(invocation=pb.Invocation(status="SUCCEEDED", result="hello")),
    ]
    assert asyncio.run(agent.invoke("hi")) == "hello"
    assert agent.duplicate().state.thread_id != agent.state.thread_id
    assert transport.call.call_args_list[0].args[1].prompt == "hi"


def test_lost_submit_reply_exposes_handle_without_replaying():
    agent, transport = proxy()
    transport.call.side_effect = asyncio.TimeoutError()
    with pytest.raises(SubmissionUncertain) as exc:
        asyncio.run(agent.submit("hi", invocation_id="stable"))
    assert exc.value.handle.invocation_id == "stable"
    transport.call.assert_awaited_once()


def test_stream_preserves_sse_event_shape():
    agent, transport = proxy()
    transport.call.side_effect = [
        pb.SubmitResponse(invocation=pb.Invocation(owner_instance_id="one")),
        pb.StatusResponse(
            invocation=pb.Invocation(
                status="SUCCEEDED",
                events=[
                    pb.AgentEvent(sequence=1, event="ai_message", data="hello"),
                    pb.AgentEvent(sequence=2, event="final_state", data="hello"),
                ],
            )
        ),
    ]

    async def scenario():
        return [e async for e in agent.stream_invoke("hi")]

    assert asyncio.run(scenario()) == [
        {"event": "ai_message", "data": "hello"},
        {"event": "final_state", "data": "hello"},
    ]


def test_completed_stream_replays_all_pages():
    agent, transport = proxy()
    transport.call.side_effect = [
        pb.StatusResponse(
            invocation=pb.Invocation(
                status="SUCCEEDED",
                last_sequence=2,
                events=[pb.AgentEvent(sequence=1, event="message", data="first")],
            )
        ),
        pb.StatusResponse(
            invocation=pb.Invocation(
                status="SUCCEEDED",
                last_sequence=2,
                events=[pb.AgentEvent(sequence=2, event="done", data="[DONE]")],
            )
        ),
    ]

    async def scenario():
        return [e async for e in agent.invocation("existing").events()]

    assert len(asyncio.run(scenario())) == 2
    assert transport.call.call_args_list[1].args[1].after_sequence == 1


def test_tools_preserve_parent_thread_and_support_worker_threads():
    pytest.importorskip("langchain_core")
    from naas_abi_sdk.agent_tools import agent_tools

    class FakeProxy:
        name = "remote"
        description = "Remote tool"
        state = SimpleNamespace(thread_id="default")

        def duplicate(self, agent_shared_state):
            result = FakeProxy()
            result.state = agent_shared_state
            return result

        async def invoke(self, prompt):
            return self.state.thread_id + ":" + prompt

    async def scenario():
        tool = agent_tools(FakeProxy())[0]
        config = {"configurable": {"thread_id": "parent"}}
        assert await tool.ainvoke({"prompt": "hello"}, config=config) == "parent:hello"
        assert (
            await asyncio.to_thread(tool.invoke, {"prompt": "hello"}, config=config)
            == "parent:hello"
        )
        with pytest.raises(RuntimeError, match="ainvoke"):
            tool.invoke({"prompt": "hello"}, config=config)

    asyncio.run(scenario())
