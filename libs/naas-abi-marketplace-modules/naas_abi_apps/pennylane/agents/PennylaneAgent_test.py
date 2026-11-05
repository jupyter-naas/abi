"""Offline: the module builds its agent on fake engine services and serves it."""

from __future__ import annotations

import asyncio
from types import SimpleNamespace

from langchain_core.language_models.chat_models import BaseChatModel
from langchain_core.messages import AIMessage
from langchain_core.outputs import ChatGeneration, ChatResult
from naas_abi_apps.pennylane import ABIModule
from naas_abi_apps.pennylane.agents.PennylaneAgent import NAME, create_agent
from naas_abi_sdk.agent_host import InvocationContext


class EchoModel(BaseChatModel):
    tools: list = []

    @property
    def _llm_type(self) -> str:
        return "echo"

    def bind_tools(self, tools, **kwargs):
        self.tools = list(tools)
        return self

    def _generate(self, messages, stop=None, run_manager=None, **kwargs):
        return ChatResult(
            generations=[ChatGeneration(message=AIMessage("Pennylane here"))]
        )


class Registry:
    def __init__(self) -> None:
        self.model = EchoModel()
        self.asked: list[str] = []

    async def get_default_chat_model(self):
        self.asked.append("")
        return SimpleNamespace(model=self.model)

    async def get_chat_model(self, name: str):
        self.asked.append(name)
        return SimpleNamespace(model=self.model)


class Documents:
    async def ensure_collection(self, request) -> None:
        return None


class Secrets:
    def __init__(self, values: dict[str, str]) -> None:
        self.values = values

    async def get(self, key: str, default=None):
        return self.values.get(key, default)


def engine(secrets: dict[str, str]) -> SimpleNamespace:
    return SimpleNamespace(
        services=SimpleNamespace(
            model_registry=Registry(),
            document=Documents(),
            secret=Secrets(secrets),
            object_storage=SimpleNamespace(),
        )
    )


def test_on_initialized_exposes_the_agent_with_tools_from_the_secret() -> None:
    fake = engine({"PENNYLANE_API_KEY": "token"})
    module = ABIModule(fake, ABIModule.Configuration())

    asyncio.run(module.on_initialized())

    assert set(module._agent_handlers) == {NAME}
    tool_names = {tool.name for tool in fake.services.model_registry.model.tools}
    assert "pennylane_list_customers" in tool_names


def test_without_the_secret_the_agent_has_no_pennylane_tools() -> None:
    fake = engine({})
    module = ABIModule(fake, ABIModule.Configuration(chat_model="some/model"))

    asyncio.run(module.on_initialized())

    assert fake.services.model_registry.asked == ["some/model"]
    tool_names = {tool.name for tool in fake.services.model_registry.model.tools}
    assert not any(name.startswith("pennylane_") for name in tool_names)


def test_the_agent_answers_through_its_handler(monkeypatch) -> None:
    from langgraph.checkpoint.memory import InMemorySaver
    from naas_abi_apps.pennylane.agents import PennylaneAgent

    async def in_memory(documents, agent_id):
        return InMemorySaver()

    # The Document Service checkpointer is the SDK's, tested there.
    monkeypatch.setattr(PennylaneAgent, "document_memory", in_memory)

    async def scenario() -> str:
        agent = await create_agent(engine({}), "applications.pennylane", api_key=None)
        return await agent.as_handler().invoke(
            "What is your name?", InvocationContext("inv", "t1", "caller")
        )

    assert asyncio.run(scenario()) == "Pennylane here"
