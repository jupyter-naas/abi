import asyncio
from types import SimpleNamespace
from unittest.mock import Mock

from naas_abi_core.services.agent.RemoteAgentAdapter import RemoteAgentAdapter


def test_existing_agent_and_intent_surface_keeps_thread_and_sse_values():
    original = Mock()
    duplicate = original.duplicate.return_value
    duplicate.invoke.return_value = "answer"
    duplicate.stream_invoke.return_value = iter(
        [{"event": "message", "data": "answer"}, {"event": "done", "data": "[DONE]"}]
    )

    async def scenario():
        adapter = RemoteAgentAdapter(original)
        context = SimpleNamespace(
            thread_id="isolated-thread", cancelled=asyncio.Event()
        )
        assert await adapter.invoke("prompt", context) == "answer"
        assert [e async for e in adapter.stream_invoke("prompt", context)] == [
            {"event": "message", "data": "answer"},
            {"event": "done", "data": "[DONE]"},
        ]
        assert (
            original.duplicate.call_args.kwargs["agent_shared_state"].thread_id
            == "isolated-thread"
        )

    asyncio.run(scenario())


def test_streamed_events_keep_event_data_and_a_chat_source_opt_out_only():
    original = Mock()
    original.duplicate.return_value.stream_invoke.return_value = iter(
        [
            {"event": "tool_response", "data": "a", "chat_source": True},
            {"event": "tool_response", "data": "b", "chat_source": False},
            {"event": "message", "data": "answer", "in_process_only": object()},
        ]
    )

    async def scenario():
        context = SimpleNamespace(thread_id="thread", cancelled=asyncio.Event())
        return [
            e async for e in RemoteAgentAdapter(original).stream_invoke("p", context)
        ]

    # The SDK host refuses any other key (INVALID_STREAM) and fails the run.
    assert asyncio.run(scenario()) == [
        {"event": "tool_response", "data": "a"},
        {"event": "tool_response", "data": "b", "chat_source": False},
        {"event": "message", "data": "answer"},
    ]


def test_cancel_waits_for_sync_worker_before_returning():
    from threading import Event

    import pytest

    started, finish = Event(), Event()
    original = Mock()

    def invoke(prompt):
        started.set()
        finish.wait(3)
        return "finished"

    original.duplicate.return_value.invoke.side_effect = invoke

    async def scenario():
        context = SimpleNamespace(thread_id="thread", cancelled=asyncio.Event())
        task = asyncio.create_task(
            RemoteAgentAdapter(original).invoke("prompt", context)
        )
        assert await asyncio.to_thread(started.wait, 2)
        task.cancel()
        await asyncio.sleep(0.02)
        assert not task.done()
        assert context.cancelled.is_set()
        finish.set()
        with pytest.raises(asyncio.CancelledError):
            await task

    asyncio.run(scenario())


def _until_stopped() -> bool:
    import time

    from naas_abi_core.services.agent.context import turn_stopped

    for _ in range(300):
        if turn_stopped():
            return True
        time.sleep(0.01)
    return False


def test_cancel_stops_the_run_at_its_next_step():
    import pytest

    seen: list[bool] = []
    original = Mock()
    original.duplicate.return_value.invoke.side_effect = lambda _prompt: (
        seen.append(_until_stopped()) or "stopped"
    )

    async def scenario():
        context = SimpleNamespace(thread_id="thread", cancelled=asyncio.Event())
        task = asyncio.create_task(RemoteAgentAdapter(original).invoke("p", context))
        await asyncio.sleep(0.05)
        task.cancel()
        with pytest.raises(asyncio.CancelledError):
            await task

    asyncio.run(scenario())
    assert seen == [True]


def test_a_stream_left_by_its_caller_stops_the_run():
    seen: list[bool] = []

    def stream_invoke(_prompt):
        yield {"event": "tool_usage", "data": "search_files"}
        seen.append(_until_stopped())
        yield {"event": "message", "data": "late"}

    original = Mock()
    original.duplicate.return_value.stream_invoke.side_effect = stream_invoke

    async def scenario():
        context = SimpleNamespace(thread_id="thread", cancelled=asyncio.Event())
        events = RemoteAgentAdapter(original).stream_invoke("p", context)
        assert (await anext(events))["data"] == "search_files"
        await events.aclose()
        assert context.cancelled.is_set()

    asyncio.run(scenario())
    assert seen == [True]
