"""Expose an existing Agent or IntentAgent through the standalone async host.

The SDK never imports this adapter. Only the provider needs ABI core. Cancellation
waits for synchronous inference to finish, so its conversation claim is not freed
while the worker thread can still perform side effects.
"""

from __future__ import annotations

import asyncio
from collections.abc import AsyncIterator
from typing import Any, Protocol

from naas_abi_core.services.agent.Agent import Agent, AgentSharedState


class RemoteInvocationContext(Protocol):
    thread_id: str
    cancelled: asyncio.Event


class RemoteAgentAdapter:
    def __init__(self, agent: Agent):
        self.agent = agent

    async def invoke(self, prompt: str, context: RemoteInvocationContext) -> str:
        def execute() -> str:
            agent = self.agent.duplicate(
                agent_shared_state=AgentSharedState(thread_id=context.thread_id)
            )
            return agent.invoke(prompt)

        task = asyncio.create_task(asyncio.to_thread(execute))
        try:
            return await asyncio.shield(task)
        except asyncio.CancelledError:
            context.cancelled.set()
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

        def produce() -> None:
            agent = self.agent.duplicate(
                agent_shared_state=AgentSharedState(thread_id=context.thread_id)
            )
            for event in agent.stream_invoke(prompt):
                if not context.cancelled.is_set():
                    asyncio.run_coroutine_threadsafe(deliver(event), loop).result()

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
            await asyncio.shield(task)
