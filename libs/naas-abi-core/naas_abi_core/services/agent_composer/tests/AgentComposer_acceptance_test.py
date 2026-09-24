"""End-to-end: agents composed without an agent Python file, then run.

Covers the issue's acceptance scenarios with real services wired as the
engine wires them (model registry, tool registry with a model-registry
embedder, file-backed records, secret resolution). Only the LLMs are scripted.
"""

from __future__ import annotations

import json
from collections.abc import Mapping
from typing import Any

import pytest
from langchain_core.messages import AIMessage, SystemMessage
from langchain_core.tools import BaseTool, StructuredTool, tool
from langgraph.checkpoint.memory import MemorySaver
from pydantic import BaseModel

from naas_abi_core.models.Model import ChatModel
from naas_abi_core.services.agent.Agent import (
    Agent,
    AgentConfiguration,
    AgentSharedState,
)
from naas_abi_core.services.agent.CapabilityAgent import CapabilityAgent
from naas_abi_core.services.agent.tests.scripted_chat_model import (
    ScriptedChatModel,
    tool_call,
)
from naas_abi_core.services.agent_composer.adapters.secondary.FileSystemAgentSpecRepositoryAdapter import (
    FileSystemAgentSpecRepositoryAdapter,
)
from naas_abi_core.services.agent_composer.adapters.secondary.MappingSecretResolverAdapter import (
    MappingSecretResolverAdapter,
)
from naas_abi_core.services.agent_composer.AgentComposerService import (
    AgentComposerService,
)
from naas_abi_core.services.model_registry.ModelRegistryService import (
    ModelRegistryService,
)
from naas_abi_core.services.tool_registry.adapters.primary.LangChainToolPublisher import (
    ToolPublisher,
)
from naas_abi_core.services.tool_registry.tests.concept_embeddings import (
    concept_embedding_model,
)
from naas_abi_core.services.tool_registry.ToolRegistryFactory import ToolRegistryFactory
from naas_abi_core.services.tool_registry.ToolRegistryPort import ConfigRequirement

TRACKER = "acme.tracker"
WEATHER = "acme.weather"

tickets: list[dict[str, str]] = []


class _TicketArgs(BaseModel):
    title: str


def _tracker_tools(configuration: Mapping[str, Any]) -> list[BaseTool]:
    """An integration-style ``as_tools(configuration)``: needs a token."""
    token = configuration["api_token"]

    def create_ticket(title: str) -> str:
        tickets.append({"title": title, "token": token})
        return f"ticket '{title}' created"

    return [
        StructuredTool(
            name="create_ticket",
            description="Create a new issue in the bug tracker.",
            func=create_ticket,
            args_schema=_TicketArgs,
        )
    ]


@tool
def get_forecast(city: str) -> str:
    """Get the weather forecast for a city.

    Args:
        city: The city.
    """
    return f"sunny in {city}"


@pytest.fixture(autouse=True)
def _reset():
    tickets.clear()


def _scripted(
    model_id: str, script: list[AIMessage]
) -> tuple[ChatModel, ScriptedChatModel]:
    llm = ScriptedChatModel.from_script(script)
    return ChatModel(model_id=model_id, provider="test", model=llm), llm


@pytest.fixture
def models() -> ModelRegistryService:
    registry = ModelRegistryService(
        default_chat_model="default-model", default_embedding_model="concepts"
    )
    registry.register("concepts", concept_embedding_model())
    registry.register(
        "default-model", _scripted("default-model", [AIMessage(content="default")])[0]
    )
    return registry


@pytest.fixture
def tools(models):
    # Built the way the engine builds it: search through the model registry.
    registry = ToolRegistryFactory.InMemory(models)
    tracker = ToolPublisher(TRACKER)
    tracker.add_factory(
        _tracker_tools,
        requirements=[ConfigRequirement(key="api_token", secret=True)],
    )
    tracker.publish_to(registry)
    weather = ToolPublisher(WEATHER)
    weather.add_tool(get_forecast)
    weather.publish_to(registry)
    return registry


@pytest.fixture
def records(tmp_path):
    return tmp_path / "agents"


@pytest.fixture
def composer(models, tools, records) -> AgentComposerService:
    return AgentComposerService(
        tool_registry=tools,
        model_registry=models,
        spec_repository=FileSystemAgentSpecRepositoryAdapter(records),
        secret_resolver=MappingSecretResolverAdapter(
            {"TRACKER_TOKEN": "tracker-secret"}
        ),
        memory_factory=MemorySaver,
    )


def test_a_stored_record_runs_with_its_model_prompt_tool_and_sub_agent(
    composer, models, records
):
    triage_model, triage_llm = _scripted(
        "triage-model",
        [
            tool_call("create_ticket", {"title": "Login crash"}, "c1"),
            tool_call("transfer_to_researcher", {}, "h1"),
        ],
    )
    research_model, research_llm = _scripted(
        "research-model", [AIMessage(content="Root cause: expired session token.")]
    )
    models.register("triage-model", triage_model)
    models.register("research-model", research_model)

    records.mkdir()
    (records / "triage.yaml").write_text(
        "kind: abi.agent/v1\n"
        "name: triage\n"
        "description: Files bug reports and asks for a root cause.\n"
        "prompt: You triage bug reports. File a ticket, then ask the researcher.\n"
        "model: triage-model\n"
        "tools:\n"
        f"  - tool: {TRACKER}/create_ticket\n"
        "    config:\n"
        "      api_token: {secret: TRACKER_TOKEN}\n"
        "sub_agents:\n"
        "  - researcher\n"
    )
    (records / "researcher.yaml").write_text(
        "name: researcher\n"
        "description: Finds root causes.\n"
        "prompt: You find the root cause of bugs.\n"
        "model: research-model\n"
    )

    agent = composer.compose("triage")
    answer = agent.invoke("Users get logged out when they sign in.")

    assert answer == "Root cause: expired session token."
    # The registry tool ran with the secret the record referenced.
    assert tickets == [{"title": "Login crash", "token": "tracker-secret"}]
    # Each agent ran on its own model with its own prompt.
    first_call = triage_llm.recorder.seen[0]
    assert isinstance(first_call[0], SystemMessage)
    assert "You triage bug reports" in first_call[0].content
    assert "create_ticket" in triage_llm.recorder.bound[0]
    assert "You find the root cause" in research_llm.recorder.seen[0][0].content


def test_a_programmatic_agent_delegates_to_an_existing_agent_instance(composer, models):
    calculator = Agent(
        name="calculator",
        description="Does arithmetic.",
        chat_model=ScriptedChatModel.from_script([AIMessage(content="42")]),
        memory=MemorySaver(),
        state=AgentSharedState(thread_id="calculator"),
        configuration=AgentConfiguration(system_prompt="You compute."),
    )
    lead_model, _ = _scripted(
        "lead-model", [tool_call("transfer_to_calculator", {}, "h1")]
    )
    models.register("lead-model", lead_model)

    lead = composer.create(
        name="lead",
        prompt="You delegate arithmetic to the calculator.",
        model="lead-model",
        sub_agents=[calculator],
    )

    assert lead.invoke("What is 6 times 7?") == "42"
    assert calculator.state.thread_id == "calculator"


def test_a_composed_agent_discovers_enables_and_uses_a_tool(composer, models, records):
    seeker_model, seeker_llm = _scripted(
        "seeker-model",
        [
            tool_call("search_capabilities", {"query": "report a defect"}, "s1"),
            tool_call(
                "enable_capability", {"tool_id": f"{TRACKER}/create_ticket@1"}, "e1"
            ),
            tool_call("create_ticket", {"title": "Crash on save"}, "c1"),
            AIMessage(content="Filed."),
        ],
    )
    models.register("seeker-model", seeker_model)
    records.mkdir()
    (records / "seeker.yaml").write_text(
        "name: seeker\n"
        "prompt: Find the tools you need, then use them.\n"
        "model: seeker-model\n"
        "capabilities:\n"
        "  enabled: true\n"
        f"  allow: ['{TRACKER}/*']\n"
        "  tool_config:\n"
        f"    {TRACKER}/create_ticket@1:\n"
        "      api_token: {secret: TRACKER_TOKEN}\n"
    )

    agent = composer.compose("seeker")
    assert isinstance(agent, CapabilityAgent)
    assert agent.invoke("The app crashes when I save.") == "Filed."

    found = json.loads(seeker_llm.recorder.tool_messages(1)[0].content)
    assert found[0]["tool_id"] == f"{TRACKER}/create_ticket@1"
    assert "create_ticket" not in seeker_llm.recorder.bound[1]
    assert "create_ticket" in seeker_llm.recorder.bound[2]
    assert tickets == [{"title": "Crash on save", "token": "tracker-secret"}]


def test_a_nested_record_tree_keeps_routing_on_the_next_turn(composer, models, records):
    """lead -> manager -> worker: the follow-up turn must reach the worker
    through the manager, since the lead's graph only holds its own children."""
    lead_model, lead_llm = _scripted(
        "lead-model", [tool_call("transfer_to_manager", {}, "h1")]
    )
    manager_model, _ = _scripted(
        "manager-model", [tool_call("transfer_to_worker", {}, "h2")]
    )
    worker_model, _ = _scripted(
        "worker-model",
        [AIMessage(content="first answer"), AIMessage(content="follow-up answer")],
    )
    models.register("lead-model", lead_model)
    models.register("manager-model", manager_model)
    models.register("worker-model", worker_model)
    records.mkdir()
    (records / "lead.yaml").write_text(
        "name: lead\nprompt: You lead.\nmodel: lead-model\nsub_agents: [manager]\n"
    )
    (records / "manager.yaml").write_text(
        "name: manager\nprompt: You manage.\nmodel: manager-model\n"
        "sub_agents: [worker]\n"
    )
    (records / "worker.yaml").write_text(
        "name: worker\nprompt: You do the work.\nmodel: worker-model\n"
    )

    lead = composer.compose("lead")
    assert lead.invoke("do the task") == "first answer"
    assert lead.invoke("and a follow-up") == "follow-up answer"
    # The lead did not have to route the follow-up again.
    assert len(lead_llm.recorder.bound) == 1
