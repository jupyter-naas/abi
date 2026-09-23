from __future__ import annotations

from collections.abc import Mapping
from typing import Any

import pytest
from langchain_core.messages import AIMessage
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
from naas_abi_core.services.agent.tests.scripted_chat_model import ScriptedChatModel
from naas_abi_core.services.agent_composer.adapters.secondary.InMemoryAgentSpecRepositoryAdapter import (
    InMemoryAgentSpecRepositoryAdapter,
)
from naas_abi_core.services.agent_composer.adapters.secondary.MappingSecretResolverAdapter import (
    MappingSecretResolverAdapter,
)
from naas_abi_core.services.agent_composer.AgentComposerPort import (
    AgentCompositionError,
    AgentSpec,
    AgentSpecNotFoundError,
    SubAgentCycleError,
    ToolNameCollisionError,
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
from naas_abi_core.services.tool_registry.ToolRegistryPort import (
    ConfigRequirement,
    ToolContext,
)
from naas_abi_core.services.tool_registry.ToolRegistryService import (
    ToolRegistryService,
)

GITHUB = "acme.github"
TRACKER = "acme.tracker"


@tool
def get_repository(repo_name: str) -> str:
    """Get a repository.

    Args:
        repo_name: Full repository name.
    """
    return repo_name


@tool
def get_time_date() -> str:
    """Shadows a default tool of every agent."""
    return "never"


class _TicketArgs(BaseModel):
    title: str


def _tracker_tools(configuration: Mapping[str, Any]) -> list[BaseTool]:
    token = configuration["api_token"]
    return [
        StructuredTool(
            name="create_ticket",
            description="Create a ticket in the tracker.",
            func=lambda title: f"{token}:{title}",
            args_schema=_TicketArgs,
        )
    ]


def _chat(model_id: str) -> ChatModel:
    return ChatModel(
        model_id=model_id,
        provider="test",
        model=ScriptedChatModel.from_script([AIMessage(content=f"hi from {model_id}")]),
    )


@pytest.fixture
def model_registry() -> ModelRegistryService:
    registry = ModelRegistryService(default_chat_model="default-model")
    registry.register("default-model", _chat("default-model"))
    registry.register("fast-model", _chat("fast-model"))
    return registry


@pytest.fixture
def tool_registry() -> ToolRegistryService:
    registry = ToolRegistryService()
    github = ToolPublisher(GITHUB)
    github.add_tool(get_repository)
    github.add_tool(
        StructuredTool.from_function(
            func=lambda repo_name: repo_name,
            name="delete_repository",
            description="Delete a repository.",
        ),
        required_scopes=("github:admin",),
    )
    github.publish_to(registry)
    tracker = ToolPublisher(TRACKER)
    tracker.add_factory(
        _tracker_tools,
        default_config={},
        requirements=[ConfigRequirement(key="api_token", secret=True)],
    )
    tracker.publish_to(registry)
    return registry


@pytest.fixture
def repository() -> InMemoryAgentSpecRepositoryAdapter:
    return InMemoryAgentSpecRepositoryAdapter()


@pytest.fixture
def composer(model_registry, tool_registry, repository) -> AgentComposerService:
    return AgentComposerService(
        tool_registry=tool_registry,
        model_registry=model_registry,
        spec_repository=repository,
        secret_resolver=MappingSecretResolverAdapter({"TRACKER_TOKEN": "s3cret"}),
        memory_factory=MemorySaver,
    )


def _spec(**values: Any) -> AgentSpec:
    return AgentSpec.model_validate(
        {"name": "triage", "prompt": "You triage.", **values}
    )


def _tool_names(agent: Agent) -> set[str]:
    return {t.name for t in agent.tools}


# --------------------------------------------------------------------------- #
# Model and prompt                                                             #
# --------------------------------------------------------------------------- #


class TestModelAndPrompt:
    def test_minimal_record_uses_the_default_model_and_the_prompt(self, composer):
        agent = composer.compose(_spec(description="Triage bugs"))
        assert isinstance(agent, Agent) and not isinstance(agent, CapabilityAgent)
        assert agent.name == "triage"
        assert agent.description == "Triage bugs"
        assert agent.configuration.get_system_prompt([]) == "You triage."
        assert agent.invoke("hello") == "hi from default-model"

    def test_a_referenced_model_is_resolved_through_the_registry(self, composer):
        agent = composer.compose(_spec(model="fast-model"))
        assert agent.invoke("hello") == "hi from fast-model"

    def test_an_unknown_model_is_a_composition_problem(self, composer):
        with pytest.raises(AgentCompositionError, match="missing-model"):
            composer.compose(_spec(model="missing-model"))

    def test_each_composition_gets_its_own_conversation(self, composer):
        first = composer.compose(_spec())
        second = composer.compose(_spec())
        assert first.state.thread_id != second.state.thread_id


# --------------------------------------------------------------------------- #
# Tools                                                                        #
# --------------------------------------------------------------------------- #


class TestTools:
    def test_registry_tools_are_bound(self, composer):
        agent = composer.compose(_spec(tools=[f"{GITHUB}/get_repository"]))
        assert "get_repository" in _tool_names(agent)

    def test_secret_references_are_resolved_into_the_binding(self, composer):
        agent = composer.compose(
            _spec(
                tools=[
                    {
                        "tool": f"{TRACKER}/create_ticket",
                        "config": {"api_token": {"secret": "TRACKER_TOKEN"}},
                    }
                ]
            )
        )
        ticket = next(t for t in agent.tools if t.name == "create_ticket")
        assert ticket.invoke({"title": "bug"}) == "s3cret:bug"

    def test_every_problem_is_reported_at_once(self, composer):
        with pytest.raises(AgentCompositionError) as error:
            composer.compose(
                _spec(
                    model="missing-model",
                    tools=[
                        f"{GITHUB}/unknown_tool",
                        f"{GITHUB}/delete_repository",
                        f"{TRACKER}/create_ticket",
                        {
                            "tool": f"{TRACKER}/create_ticket@1",
                            "config": {"api_token": {"secret": "UNSET"}},
                        },
                    ],
                )
            )
        problems = "\n".join(error.value.problems)
        assert "missing-model" in problems
        assert "unknown_tool" in problems
        assert "github:admin" in problems  # access denied
        assert "api_token" in problems  # missing configuration
        assert "UNSET" in problems  # secret not set
        assert len(error.value.problems) == 5

    def test_credentials_must_be_secret_references(self, composer):
        with pytest.raises(AgentCompositionError, match="secret"):
            composer.compose(
                _spec(
                    tools=[
                        {
                            "tool": f"{TRACKER}/create_ticket",
                            "config": {"api_token": "sk-live"},
                        }
                    ]
                )
            )

    def test_the_caller_context_grants_scoped_tools(self, composer):
        agent = composer.compose(
            _spec(tools=[f"{GITHUB}/delete_repository"]),
            context=ToolContext(scopes={"github:admin"}),
        )
        assert "delete_repository" in _tool_names(agent)

    def test_inline_tools_are_accepted_next_to_registry_tools(self, composer):
        @tool
        def ping() -> str:
            """Ping."""
            return "pong"

        agent = composer.compose(
            _spec(tools=[f"{GITHUB}/get_repository"]), tools=[ping]
        )
        assert {"ping", "get_repository"} <= _tool_names(agent)

    def test_two_tools_with_one_model_facing_name_collide(
        self, composer, tool_registry
    ):
        clone = ToolPublisher("acme.clone")
        clone.add_tool(get_repository)
        clone.publish_to(tool_registry)
        with pytest.raises(ToolNameCollisionError, match="get_repository"):
            composer.compose(
                _spec(tools=[f"{GITHUB}/get_repository", "acme.clone/get_repository"])
            )

    def test_a_tool_shadowing_a_default_tool_collides(self, composer):
        with pytest.raises(ToolNameCollisionError, match="get_time_date"):
            composer.compose(_spec(), tools=[get_time_date])


# --------------------------------------------------------------------------- #
# Sub-agents                                                                   #
# --------------------------------------------------------------------------- #


class TestSubAgents:
    def test_record_sub_agents_are_composed_and_supervised(self, composer, repository):
        repository.save(
            AgentSpec(
                name="researcher",
                prompt="You research.",
                tools=[f"{GITHUB}/get_repository"],
            )
        )
        agent = composer.compose(_spec(sub_agents=["researcher"]))

        (researcher,) = agent.agents
        assert researcher.name == "researcher"
        assert "get_repository" in _tool_names(researcher)
        assert "transfer_to_researcher" in _tool_names(agent)
        assert researcher.state is agent.state
        assert agent.state.supervisor_agent == "triage"
        assert "request_help" in _tool_names(researcher)

    def test_nested_records_compose_recursively(self, composer, repository):
        repository.save(AgentSpec(name="leaf", prompt="Leaf."))
        repository.save(AgentSpec(name="middle", prompt="Middle.", sub_agents=["leaf"]))
        agent = composer.compose(_spec(sub_agents=["middle"]))
        assert agent.agents[0].agents[0].name == "leaf"

    def test_cycles_are_rejected_with_their_path(self, composer, repository):
        repository.save(AgentSpec(name="a", prompt="A.", sub_agents=["b"]))
        repository.save(AgentSpec(name="b", prompt="B.", sub_agents=["a"]))
        with pytest.raises(SubAgentCycleError) as error:
            composer.compose("a")
        assert error.value.cycle == ("a", "b", "a")

    def test_a_record_referencing_itself_is_a_cycle(self, composer):
        with pytest.raises(SubAgentCycleError, match="triage -> triage"):
            composer.compose(_spec(sub_agents=["triage"]))

    def test_unknown_sub_agent_record_is_reported(self, composer):
        with pytest.raises(AgentCompositionError, match="ghost"):
            composer.compose(_spec(sub_agents=["ghost"]))

    def test_sub_agent_records_need_a_repository(self, model_registry, tool_registry):
        composer = AgentComposerService(tool_registry, model_registry)
        with pytest.raises(AgentCompositionError, match="repository"):
            composer.compose(_spec(sub_agents=["researcher"]))

    def test_existing_instances_become_sub_agents_without_being_mutated(self, composer):
        existing = Agent(
            name="calculator",
            description="Does math",
            chat_model=ScriptedChatModel.from_script([AIMessage(content="42")]),
            memory=MemorySaver(),
            state=AgentSharedState(thread_id="theirs"),
            configuration=AgentConfiguration(system_prompt="You compute."),
        )
        agent = composer.compose(_spec(), sub_agents=[existing])

        (calculator,) = agent.agents
        assert calculator is not existing
        assert calculator.name == "calculator"
        assert calculator.state is agent.state
        assert existing.state.thread_id == "theirs"
        assert existing.state.supervisor_agent is None

    def test_duplicate_sub_agent_names_are_rejected(self, composer, repository):
        repository.save(AgentSpec(name="calculator", prompt="Math."))
        existing = composer.compose(AgentSpec(name="calculator", prompt="Math."))
        with pytest.raises(AgentCompositionError, match="calculator"):
            composer.compose(_spec(sub_agents=["calculator"]), sub_agents=[existing])


# --------------------------------------------------------------------------- #
# Records and programmatic creation                                            #
# --------------------------------------------------------------------------- #


class TestEntryPoints:
    def test_compose_by_record_name(self, composer, repository):
        repository.save(_spec())
        assert composer.compose("triage").name == "triage"

    def test_compose_by_unknown_name(self, composer):
        with pytest.raises(AgentSpecNotFoundError):
            composer.compose("nobody")

    def test_create_builds_the_same_agent_programmatically(self, composer):
        existing = composer.compose(AgentSpec(name="helper", prompt="Help."))

        @tool
        def ping() -> str:
            """Ping."""
            return "pong"

        agent = composer.create(
            name="lead",
            prompt="You lead.",
            description="Leads",
            model="fast-model",
            tools=[f"{GITHUB}/get_repository", ping],
            sub_agents=[existing],
        )
        assert agent.name == "lead"
        assert {"get_repository", "ping", "transfer_to_helper"} <= _tool_names(agent)
        assert [a.name for a in agent.agents] == ["helper"]
        assert agent.invoke("hello") == "hi from fast-model"

    def test_capabilities_produce_a_capability_agent(self, composer):
        agent = composer.compose(
            _spec(
                capabilities={
                    "enabled": True,
                    "allow": [f"{TRACKER}/*"],
                    "max_enabled": 2,
                    "tool_config": {
                        f"{TRACKER}/create_ticket@1": {
                            "api_token": {"secret": "TRACKER_TOKEN"}
                        }
                    },
                }
            )
        )
        assert isinstance(agent, CapabilityAgent)
        assert agent.allow == (f"{TRACKER}/*",)
        assert agent.max_enabled == 2
        assert {"search_capabilities", "enable_capability"} <= _tool_names(agent)

    def test_capability_tool_config_secrets_must_resolve(self, composer):
        with pytest.raises(AgentCompositionError, match="UNSET"):
            composer.compose(
                _spec(
                    capabilities={
                        "enabled": True,
                        "tool_config": {
                            f"{TRACKER}/create_ticket@1": {
                                "api_token": {"secret": "UNSET"}
                            }
                        },
                    }
                )
            )
