"""M, Market Intelligence's stand-in: one app, ``prices`` (``apps/prices``), and
one agent, ``Pricer`` (the cast of issue #1413), which answers without a model."""

from __future__ import annotations

import asyncio

from naas_abi_sdk import AgentDescriptor, BaseModule, ModuleDependencies

AGENT_INVOKE = ("agent.invoke.v1",)


class EchoAgent:
    """An agent that needs no model: it says who answered."""

    def __init__(self, name: str) -> None:
        self.name = name

    async def answer(self, prompt: str) -> str:
        request = (prompt.strip().splitlines() or [""])[-1].strip()
        return f"{self.name} of dev.market answers: {request}"

    async def invoke(self, prompt, context):
        return await self.answer(str(prompt))

    async def stream_invoke(self, prompt, context):
        yield {"event": "message", "data": await self.answer(str(prompt))}
        yield {"event": "done", "data": "[DONE]"}


class ABIModule(BaseModule):
    module_id = "dev.market"
    package_version = "0.1.0"
    # A manifest holds at least one statement: its own documents.
    dependencies = ModuleDependencies(services=("document",))
    agents = (AgentDescriptor("Pricer", "The agent of M", capabilities=AGENT_INVOKE),)

    async def on_initialized(self) -> None:
        for descriptor in self.agents:
            self.expose_agent(descriptor.name, EchoAgent(descriptor.name))

    async def run(self) -> None:
        # Its agents and apps are served in the background: stay up until stopped.
        await asyncio.Event().wait()
