"""Runtime capability discovery and activation, driven through real turns.

A scripted chat model plays the LLM and records the tools each model call was
bound with, so the tests observe exactly what "later model turns reflect the
change" means: the bound tool set, and what ``call_tools`` dispatches.
"""

from __future__ import annotations

import json
from typing import Any

import pytest
from langchain_core.messages import AIMessage, ToolMessage
from langchain_core.tools import tool
from langgraph.checkpoint.memory import MemorySaver
from naas_abi_core.services.agent.Agent import AgentConfiguration, AgentSharedState
from naas_abi_core.services.agent.CapabilityAgent import CapabilityAgent
from naas_abi_core.services.agent.tests.scripted_chat_model import (
    ScriptedChatModel,
    ScriptRecorder,
)
from naas_abi_core.services.agent.tests.scripted_chat_model import (
    tool_call as _call,
)
from naas_abi_core.services.agent.tests.scripted_chat_model import (
    tool_calls as _calls,
)
from naas_abi_core.services.tool_registry.adapters.primary.LangChainToolPublisher import (
    ToolPublisher,
)
from naas_abi_core.services.tool_registry.adapters.secondary.InMemoryToolIndexAdapter import (
    InMemoryToolIndexAdapter,
)
from naas_abi_core.services.tool_registry.tests.concept_embeddings import (
    CountingConceptEmbedder,
)
from naas_abi_core.services.tool_registry.ToolRegistryPort import ToolContext
from naas_abi_core.services.tool_registry.ToolRegistryService import (
    ToolRegistryService,
)

GITHUB = "acme.github"
WEATHER = "acme.weather"
CREATE_ISSUE = f"{GITHUB}/create_issue@1"
SECRET_ISSUE = f"{GITHUB}/create_private_issue@1"
FORECAST = f"{WEATHER}/get_forecast@1"

# --------------------------------------------------------------------------- #
# Test doubles                                                                 #
# --------------------------------------------------------------------------- #

issue_calls: list[dict[str, str]] = []


@tool
def create_issue(repo_name: str, title: str) -> str:
    """Create a new issue in a GitHub repository.

    Args:
        repo_name: Full repository name, 'owner/repo'.
        title: Title of the issue.
    """
    issue_calls.append({"repo_name": repo_name, "title": title})
    return f"created issue '{title}' in {repo_name}"


@tool
def create_private_issue(repo_name: str, title: str) -> str:
    """Create a new confidential issue in a private GitHub repository.

    Args:
        repo_name: Full repository name, 'owner/repo'.
        title: Title of the issue.
    """
    return "created"


@tool
def get_forecast(city: str) -> str:
    """Get the weather forecast for a city.

    Args:
        city: The city.
    """
    return f"sunny in {city}"


@tool
def lookup(query: str) -> str:
    """A static tool the agent always has.

    Args:
        query: What to look up.
    """
    return query


@pytest.fixture(autouse=True)
def _reset_calls():
    issue_calls.clear()


@pytest.fixture
def registry() -> ToolRegistryService:
    registry = ToolRegistryService(
        embedder=CountingConceptEmbedder(), index=InMemoryToolIndexAdapter()
    )
    github = ToolPublisher(GITHUB)
    github.add_tool(create_issue)
    github.add_tool(create_private_issue, required_scopes=("github:private",))
    github.publish_to(registry)
    weather = ToolPublisher(WEATHER)
    weather.add_tool(get_forecast)
    weather.publish_to(registry)
    return registry


def _agent(
    registry: ToolRegistryService,
    script: list[AIMessage],
    *,
    thread_id: str = "conversation-1",
    memory: MemorySaver | None = None,
    context: ToolContext | None = None,
    **options: Any,
) -> tuple[CapabilityAgent, ScriptRecorder]:
    recorder = ScriptRecorder(script)
    agent = CapabilityAgent(
        name="capability_agent",
        description="Finds and enables the tools it needs",
        chat_model=ScriptedChatModel(recorder=recorder),
        tool_registry=registry,
        tools=[lookup],
        memory=memory or MemorySaver(),
        state=AgentSharedState(thread_id=thread_id),
        configuration=AgentConfiguration(system_prompt="You are under test."),
        context_provider=(lambda: context) if context is not None else None,
        enable_default_tools=False,
        **options,
    )
    return agent, recorder


def _tool_messages(recorder: ScriptRecorder) -> list[ToolMessage]:
    return recorder.tool_messages()


CAPABILITY_TOOLS = [
    "disable_capability",
    "enable_capability",
    "list_enabled_capabilities",
    "search_capabilities",
]

# --------------------------------------------------------------------------- #
# Lifecycle                                                                    #
# --------------------------------------------------------------------------- #


def test_search_enable_invoke_disable_lifecycle(registry):
    memory = MemorySaver()
    agent, recorder = _agent(
        registry,
        [
            _call(
                "search_capabilities",
                {"query": "report a defect in our codebase"},
                "s1",
            ),
            _call("enable_capability", {"tool_id": f"{GITHUB}/create_issue"}, "e1"),
            _call("create_issue", {"repo_name": "o/r", "title": "Crash"}, "c1"),
            AIMessage(content="Filed it."),
            _call("disable_capability", {"tool_id": CREATE_ISSUE}, "d1"),
            _call("create_issue", {"repo_name": "o/r", "title": "Again"}, "c2"),
            AIMessage(content="I no longer can."),
        ],
        memory=memory,
    )

    assert agent.invoke("file a bug about the crash") == "Filed it."

    base = sorted(["lookup", *CAPABILITY_TOOLS])
    # Search and enable happen with the base tool set only...
    assert recorder.bound[0] == base
    assert recorder.bound[1] == base
    # ...and from the next model call on, the enabled tool is bound.
    assert recorder.bound[2] == sorted([*base, "create_issue"])
    assert issue_calls == [{"repo_name": "o/r", "title": "Crash"}]
    search_result = json.loads(_tool_messages(recorder)[0].content)
    assert search_result[0]["tool_id"] == CREATE_ISSUE

    # A later turn of the same conversation still has it, until disabled.
    assert agent.invoke("never mind, stop filing issues") == "I no longer can."
    assert recorder.bound[4] == sorted([*base, "create_issue"])
    assert recorder.bound[5] == base
    assert recorder.bound[6] == base
    # Dispatch reflects the change too: the second call never ran.
    assert issue_calls == [{"repo_name": "o/r", "title": "Crash"}]
    refusal = _tool_messages(recorder)[-1]
    assert "not available" in refusal.content


def test_a_selection_survives_rebuilding_the_agent_for_the_next_request(registry):
    memory = MemorySaver()
    first, _ = _agent(
        registry,
        [
            _call("enable_capability", {"tool_id": CREATE_ISSUE}, "e1"),
            AIMessage(content="ok"),
        ],
        memory=memory,
    )
    first.invoke("enable issues")

    # Each HTTP request rebuilds the agent; the selection lives in the
    # conversation checkpoint, not in the instance.
    second, recorder = _agent(
        registry,
        [
            _call("create_issue", {"repo_name": "o/r", "title": "t"}, "c1"),
            AIMessage(content="done"),
        ],
        memory=memory,
    )
    assert second.invoke("file it") == "done"
    assert "create_issue" in recorder.bound[0]
    assert issue_calls == [{"repo_name": "o/r", "title": "t"}]


def test_duplicate_keeps_registry_and_options(registry):
    agent, _ = _agent(registry, [AIMessage(content="ok")], max_enabled=3)
    copy = agent.duplicate()
    assert isinstance(copy, CapabilityAgent)
    assert copy.tool_registry is registry
    assert copy.max_enabled == 3


# --------------------------------------------------------------------------- #
# Isolation                                                                    #
# --------------------------------------------------------------------------- #


def test_enabling_in_one_conversation_does_not_leak_into_another(registry):
    memory = MemorySaver()
    a, _ = _agent(
        registry,
        [
            _call("enable_capability", {"tool_id": CREATE_ISSUE}, "e1"),
            AIMessage(content="ok"),
        ],
        memory=memory,
        thread_id="conversation-a",
    )
    a.invoke("enable issues")

    b, recorder_b = _agent(
        registry,
        [
            _call("create_issue", {"repo_name": "o/r", "title": "t"}, "c1"),
            AIMessage(content="done"),
        ],
        memory=memory,
        thread_id="conversation-b",
    )
    b.invoke("file it")

    assert "create_issue" not in recorder_b.bound[0]
    assert issue_calls == []
    # The shared registry holds definitions, never selections.
    assert [str(d.id) for d in registry.list_definitions()] == [
        f"{GITHUB}/create_issue@1",
        SECRET_ISSUE,
        FORECAST,
    ]


# --------------------------------------------------------------------------- #
# Explicit failures                                                            #
# --------------------------------------------------------------------------- #


def _enable_reply(registry, tool_id: str, **options: Any) -> tuple[str, ScriptRecorder]:
    agent, recorder = _agent(
        registry,
        [
            _call("enable_capability", {"tool_id": tool_id}, "e1"),
            AIMessage(content="ok"),
        ],
        **options,
    )
    agent.invoke("enable it")
    return str(_tool_messages(recorder)[-1].content), recorder


def test_denied_activation_is_reported_and_nothing_is_bound(registry):
    reply, recorder = _enable_reply(registry, SECRET_ISSUE)
    assert "github:private" in reply
    assert "create_private_issue" not in recorder.bound[-1]


def test_activation_is_granted_with_the_required_scope(registry):
    _, recorder = _enable_reply(
        registry, SECRET_ISSUE, context=ToolContext(scopes={"github:private"})
    )
    assert "create_private_issue" in recorder.bound[-1]


def test_unknown_tool_is_reported(registry):
    reply, _ = _enable_reply(registry, f"{GITHUB}/delete_everything")
    assert "No published tool matches" in reply


def test_tools_outside_the_allow_list_cannot_be_enabled(registry):
    reply, recorder = _enable_reply(registry, FORECAST, allow=[f"{GITHUB}/*"])
    assert "not allowed" in reply
    assert "get_forecast" not in recorder.bound[-1]


def test_search_hides_tools_outside_the_allow_list(registry):
    agent, recorder = _agent(
        registry,
        [
            _call("search_capabilities", {"query": "weather forecast"}, "s1"),
            AIMessage(content="ok"),
        ],
        allow=[f"{GITHUB}/*"],
    )
    agent.invoke("what's the weather")
    results = json.loads(_tool_messages(recorder)[-1].content)
    assert all(r["tool_id"].startswith(GITHUB) for r in results)


def test_a_name_collision_with_a_bound_tool_is_reported(registry):
    clashing = ToolPublisher("acme.other")
    clashing.add_tool(lookup)
    clashing.publish_to(registry)
    reply, _ = _enable_reply(registry, "acme.other/lookup@1")
    assert "already" in reply and "lookup" in reply


def test_the_enabled_tool_limit_is_enforced(registry):
    agent, recorder = _agent(
        registry,
        [
            _call("enable_capability", {"tool_id": CREATE_ISSUE}, "e1"),
            _call("enable_capability", {"tool_id": FORECAST}, "e2"),
            AIMessage(content="ok"),
        ],
        max_enabled=1,
    )
    agent.invoke("enable both")
    assert "limit" in _tool_messages(recorder)[-1].content
    assert "get_forecast" not in recorder.bound[-1]


def test_disabling_a_tool_that_is_not_enabled_is_reported(registry):
    agent, recorder = _agent(
        registry,
        [
            _call("disable_capability", {"tool_id": CREATE_ISSUE}, "d1"),
            AIMessage(content="ok"),
        ],
    )
    agent.invoke("disable it")
    assert "not enabled" in _tool_messages(recorder)[-1].content


def test_execution_rechecks_access_for_the_current_caller(registry):
    memory = MemorySaver()
    granted = ToolContext(user_id="alice", scopes={"github:private"})
    first, _ = _agent(
        registry,
        [
            _call("enable_capability", {"tool_id": SECRET_ISSUE}, "e1"),
            AIMessage(content="ok"),
        ],
        memory=memory,
        context=granted,
    )
    first.invoke("enable it")

    # Same conversation, but the caller has since lost the scope.
    second, recorder = _agent(
        registry,
        [
            _call("create_private_issue", {"repo_name": "o/r", "title": "t"}, "c1"),
            AIMessage(content="done"),
        ],
        memory=memory,
        context=ToolContext(user_id="alice"),
    )
    second.invoke("file it")
    assert "create_private_issue" not in recorder.bound[0]
    assert "not available" in _tool_messages(recorder)[-1].content


# --------------------------------------------------------------------------- #
# In-flight calls                                                              #
# --------------------------------------------------------------------------- #


def test_a_call_dispatched_in_the_same_step_as_its_disable_still_completes(registry):
    memory = MemorySaver()
    agent, recorder = _agent(
        registry,
        [
            _call("enable_capability", {"tool_id": CREATE_ISSUE}, "e1"),
            _calls(
                ("disable_capability", {"tool_id": CREATE_ISSUE}, "d1"),
                ("create_issue", {"repo_name": "o/r", "title": "last"}, "c1"),
            ),
            AIMessage(content="ok"),
        ],
        memory=memory,
    )
    agent.invoke("file one last issue then stop")

    # The step's calls were dispatched against the tool set it started with.
    assert issue_calls == [{"repo_name": "o/r", "title": "last"}]
    # The next model call no longer sees it.
    assert "create_issue" not in recorder.bound[-1]


# --------------------------------------------------------------------------- #
# Discovery output                                                             #
# --------------------------------------------------------------------------- #


def test_search_output_marks_enabled_tools_and_respects_the_limit(registry):
    agent, recorder = _agent(
        registry,
        [
            _call("enable_capability", {"tool_id": CREATE_ISSUE}, "e1"),
            _call("search_capabilities", {"query": "open a ticket", "limit": 1}, "s1"),
            _call("list_enabled_capabilities", {}, "l1"),
            AIMessage(content="ok"),
        ],
    )
    agent.invoke("look around")
    messages = _tool_messages(recorder)
    (result,) = json.loads(messages[-2].content)
    assert result["tool_id"] == CREATE_ISSUE
    assert result["enabled"] is True
    assert set(result) >= {"tool_id", "name", "description", "score", "available"}
    enabled = json.loads(messages[-1].content)
    assert enabled == [{"tool_id": CREATE_ISSUE, "name": "create_issue"}]
