"""Offline: the module builds its agent on fake engine services and serves it."""

from __future__ import annotations

import asyncio

from langgraph.checkpoint.memory import InMemorySaver
from naas_abi_apps.common import agents as common_agents
from naas_abi_apps.common.testing import bound_tool_names, fake_engine
from naas_abi_apps.pennylane import ABIModule
from naas_abi_apps.pennylane.agents.PennylaneAgent import NAME, create_agent
from naas_abi_sdk.agent_host import InvocationContext


def test_on_initialized_exposes_the_agent_with_tools_from_the_secret() -> None:
    engine = fake_engine({"PENNYLANE_API_KEY": "token"})
    module = ABIModule(engine, ABIModule.Configuration())

    asyncio.run(module.on_initialized())

    assert set(module._agent_handlers) == {NAME}
    assert "pennylane_list_customers" in bound_tool_names(engine)


def test_without_the_secret_the_agent_has_no_pennylane_tools() -> None:
    engine = fake_engine()
    module = ABIModule(engine, ABIModule.Configuration(chat_model="some/model"))

    asyncio.run(module.on_initialized())

    assert engine.services.model_registry.asked == ["some/model"]
    assert not any(name.startswith("pennylane_") for name in bound_tool_names(engine))


def test_the_agent_answers_through_its_handler(monkeypatch) -> None:
    async def in_memory(documents, agent_id):
        return InMemorySaver()

    # The Document Service checkpointer is the SDK's, tested there.
    monkeypatch.setattr(common_agents, "document_memory", in_memory)

    async def scenario() -> str:
        agent = await create_agent(
            fake_engine(reply="Pennylane here"), "applications.pennylane", api_key=None
        )
        return await agent.as_handler().invoke(
            "What is your name?", InvocationContext("inv", "t1", "caller")
        )

    assert asyncio.run(scenario()) == "Pennylane here"
