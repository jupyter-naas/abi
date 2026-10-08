"""Existing core agents in their own process, using only remote model proxies.

This compatibility consumer needs core for Agent/IntentAgent definitions. It does
not start an engine, construct a provider model, or require provider credentials.
"""

import asyncio
import json
import os
from pathlib import Path

from langgraph.checkpoint.memory import MemorySaver
from naas_abi_core.services.agent.Agent import Agent, AgentSharedState
from naas_abi_core.services.agent.IntentAgent import IntentAgent
from naas_abi_sdk import BaseModule, ModuleDependencies, run_module
from naas_abi_sdk.models import ChatModelProxy, EmbeddingModelProxy


class ABIModule(BaseModule):
    dependencies = ModuleDependencies(services=("model_registry",))

    async def run(self):
        registry = self.engine.services.model_registry
        chat = (await registry.get_chat_model("demo-agent-chat")).model
        embedding = (await registry.get_embedding_model("demo-embedding")).model
        assert isinstance(chat, ChatModelProxy)
        assert isinstance(embedding, EmbeddingModelProxy)
        provider_pid = int(os.environ["DEMO_MODEL_PROVIDER_PID"])
        assert provider_pid != os.getpid()
        expected = f"remote agent answer from PID {provider_pid}"
        results = []
        for agent_type in (Agent, IntentAgent):
            kwargs = {
                "name": agent_type.__name__,
                "description": "Agent using a model in another process",
                "chat_model": chat,
                "memory": MemorySaver(),
                "state": AgentSharedState(),
                "enable_default_tools": False,
            }
            if agent_type is IntentAgent:
                kwargs.update(embedding_model=embedding, enable_default_intents=False)
            agent = await asyncio.to_thread(agent_type, **kwargs)
            answer = await asyncio.to_thread(agent.invoke, "Hello from this agent")
            assert answer == expected
            events = await asyncio.to_thread(
                lambda agent=agent: list(agent.stream_invoke("Stream another answer"))
            )
            assert {"event": "message", "data": expected} in events
            results.append(
                {"agent": agent_type.__name__, "answer": answer, "stream_passed": True}
            )
        return {
            "agent_pid": os.getpid(),
            "model_provider_pid": provider_pid,
            "agents": results,
            "embedding_dimensions": len(await embedding.aembed_query("remote")),
        }


async def main():
    report = await run_module(
        ABIModule,
        url=os.environ["ABI_NATS_URL"],
        token=os.environ["ABI_SERVICE_TOKEN"],
        timeout=120,
    )
    Path(os.environ["DEMO_REPORT"]).write_text(json.dumps(report))


if __name__ == "__main__":
    asyncio.run(main())
