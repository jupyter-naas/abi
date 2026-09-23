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
