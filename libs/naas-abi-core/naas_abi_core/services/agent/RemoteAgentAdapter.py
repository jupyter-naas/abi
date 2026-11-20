"""Expose an existing Agent or IntentAgent through the standalone async host.

The SDK never imports this adapter. Only the provider needs ABI core. Cancellation
stops the run at its next step (``agent_turn_stop``) and waits for the synchronous
worker to end, so its conversation claim is not freed while the worker thread can
still perform side effects.
"""

from __future__ import annotations

import asyncio
import threading
from collections.abc import AsyncIterator
from typing import Any, Protocol

from naas_abi_core.services.agent.Agent import Agent, AgentSharedState
from naas_abi_core.services.agent.context import agent_turn_stop


class RemoteInvocationContext(Protocol):
    thread_id: str
    cancelled: asyncio.Event


def _wire_event(event: dict[str, Any]) -> dict[str, Any]:
    """The host stores and sends ``event``/``data`` and a ``chat_source``
    opt-out; any other in-process key would fail the run (INVALID_STREAM)."""
    wire = {"event": event["event"], "data": event["data"]}
    if event.get("chat_source") is False:
        wire["chat_source"] = False
    return wire


class RemoteAgentAdapter:
    def __init__(self, agent: Agent):
        self.agent = agent

    async def invoke(self, prompt: str, context: RemoteInvocationContext) -> str:
        stop = threading.Event()

        def execute() -> str:
            agent_turn_stop.set(stop)
            agent = self.agent.duplicate(
                agent_shared_state=AgentSharedState(thread_id=context.thread_id)
            )
            return agent.invoke(prompt)

        task = asyncio.create_task(asyncio.to_thread(execute))
        try:
            return await asyncio.shield(task)
        except asyncio.CancelledError:
            context.cancelled.set()
            stop.set()
            await task
            raise

    async def stream_invoke(
        self, prompt: str, context: RemoteInvocationContext
    ) -> AsyncIterator[dict[str, Any]]:
        loop = asyncio.get_running_loop()
        queue: asyncio.Queue[dict[str, Any]] = asyncio.Queue(maxsize=16)

        async def deliver(event: dict[str, Any]) -> None:
            while not context.cancelled.is_set():
                try:
                    await asyncio.wait_for(queue.put(event), 0.05)
                    return
                except TimeoutError:
                    pass

        stop = threading.Event()

        def produce() -> None:
            agent_turn_stop.set(stop)
            agent = self.agent.duplicate(
                agent_shared_state=AgentSharedState(thread_id=context.thread_id)
            )
            for event in agent.stream_invoke(prompt):
                if context.cancelled.is_set():
                    stop.set()
                else:
                    asyncio.run_coroutine_threadsafe(
                        deliver(_wire_event(event)), loop
                    ).result()

        task = asyncio.create_task(asyncio.to_thread(produce))
        try:
            while not task.done() or not queue.empty():
                try:
                    yield await asyncio.wait_for(queue.get(), 0.05)
                except TimeoutError:
                    pass
            await task
        finally:
            if not task.done():
                context.cancelled.set()
                stop.set()
            await asyncio.shield(task)
