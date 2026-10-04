import asyncio
from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest
from naas_abi_proto.agent.v1 import agent_pb2 as pb

from naas_abi_sdk.agent import AgentProxy, SubmissionUncertain
from naas_abi_sdk.discovery import AgentDescriptor


class Inbox:
    """The submitter's updates inbox: the pushed RunUpdates, then silence
    (which the client resolves with a Status read)."""

    def __init__(self, *updates):
        self.updates, self.unsubscribed = list(updates), False

    async def next_msg(self, timeout=None):
        if self.updates:
            return SimpleNamespace(data=self.updates.pop(0).SerializeToString())
        raise asyncio.TimeoutError()

    async def unsubscribe(self):
        self.unsubscribed = True


def proxy(*updates):
    descriptor = AgentDescriptor("Researcher", capabilities=("agent.invoke.v1",))
    inbox = Inbox(*updates)
    connection = SimpleNamespace(
        new_inbox=lambda: "_INBOX.test.1", subscribe=AsyncMock(return_value=inbox)
    )
    transport = SimpleNamespace(
        call=AsyncMock(), connect=AsyncMock(return_value=connection), inbox=inbox
    )
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


def operations(transport):
    return [call.args[0].rsplit(".", 1)[1] for call in transport.call.call_args_list]


def update(sequence, event, data="", parts=0):
    return pb.RunUpdate(
        event=pb.AgentEvent(sequence=sequence, event=event, data=data, parts=parts)
    )


def stream(agent):
    async def scenario():
        return [e async for e in agent.stream_invoke("hi")]

    return asyncio.run(scenario())


def test_pushed_events_need_no_polling_and_the_end_is_read_once():
    agent, transport = proxy(
        update(1, "message", "hello"),
        update(2, "done", "[DONE]"),
        pb.RunUpdate(status="SUCCEEDED", last_sequence=2),
    )
    transport.call.side_effect = [
        pb.SubmitResponse(
            invocation=pb.Invocation(owner_instance_id="one", status="RUNNING")
        ),
        pb.StatusResponse(
            invocation=pb.Invocation(status="SUCCEEDED", last_sequence=2)
        ),
    ]

    assert stream(agent) == [
        {"event": "message", "data": "hello"},
        {"event": "done", "data": "[DONE]"},
    ]
    assert operations(transport) == ["submit", "status"]
    submit, final = (c.args[1] for c in transport.call.call_args_list)
    assert submit.updates_inbox == "_INBOX.test.1"
    assert final.after_sequence == 2
    assert transport.inbox.unsubscribed


def test_a_missed_update_is_read_from_the_status():
    agent, transport = proxy(
        update(1, "message", "one"),
        update(3, "message", "three"),  # 2 was lost: at most once
        pb.RunUpdate(status="SUCCEEDED", last_sequence=3),
    )
    transport.call.side_effect = [
        pb.SubmitResponse(
            invocation=pb.Invocation(owner_instance_id="one", status="RUNNING")
        ),
        pb.StatusResponse(
            invocation=pb.Invocation(
                status="RUNNING",
                owner_available=True,
                last_sequence=3,
                events=[
                    pb.AgentEvent(sequence=2, event="message", data="two"),
                    pb.AgentEvent(sequence=3, event="message", data="three"),
                ],
            )
        ),
        pb.StatusResponse(
            invocation=pb.Invocation(status="SUCCEEDED", last_sequence=3)
        ),
    ]

    assert [e["data"] for e in stream(agent)] == ["one", "two", "three"]
    assert [c.args[1].after_sequence for c in transport.call.call_args_list[1:]] == [
        1,
        3,
    ]


def test_a_large_pushed_event_is_read_in_parts():
    agent, transport = proxy(
        update(1, "message", parts=2),
        pb.RunUpdate(status="SUCCEEDED", last_sequence=1),
    )
    transport.call.side_effect = [
        pb.SubmitResponse(
            invocation=pb.Invocation(owner_instance_id="one", status="RUNNING")
        ),
        pb.EventResponse(data=b"large "),
        pb.EventResponse(data=b"answer"),
        pb.StatusResponse(
            invocation=pb.Invocation(status="SUCCEEDED", last_sequence=1)
        ),
    ]

    assert stream(agent) == [{"event": "message", "data": "large answer"}]
    assert operations(transport) == ["submit", "event", "event", "status"]


def test_silence_is_resolved_with_the_status():
    agent, transport = proxy()  # nothing pushed: the inbox stays quiet
    transport.call.side_effect = [
        pb.SubmitResponse(
            invocation=pb.Invocation(owner_instance_id="one", status="RUNNING")
        ),
        pb.StatusResponse(
            invocation=pb.Invocation(status="RUNNING", owner_available=True)
        ),
        pb.StatusResponse(
            invocation=pb.Invocation(
                status="SUCCEEDED",
                last_sequence=1,
                events=[pb.AgentEvent(sequence=1, event="message", data="late")],
            )
        ),
    ]

    assert stream(agent) == [{"event": "message", "data": "late"}]
    assert operations(transport) == ["submit", "status", "status"]


def test_an_already_finished_resubmission_is_read_at_once():
    agent, transport = proxy()
    transport.call.side_effect = [
        pb.SubmitResponse(
            invocation=pb.Invocation(owner_instance_id="one", status="SUCCEEDED")
        ),
        pb.StatusResponse(
            invocation=pb.Invocation(
                status="SUCCEEDED",
                last_sequence=1,
                events=[pb.AgentEvent(sequence=1, event="message", data="done before")],
            )
        ),
    ]

    assert stream(agent) == [{"event": "message", "data": "done before"}]
