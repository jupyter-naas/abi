"""A module's workflow or pipeline, as an agent's tool, runs only within the
caller's module scopes (``agent_usable_module_scopes``), on a real agent turn."""

from __future__ import annotations

from types import SimpleNamespace
from typing import Any

import pytest
from langchain_core.messages import AIMessage
from langchain_core.tools import BaseTool, StructuredTool
from langgraph.checkpoint.memory import MemorySaver
from naas_abi_core.engine.engine_loaders.EngineProcessBridge import tag_process_scopes
from naas_abi_core.services.agent.Agent import (
    Agent,
    AgentConfiguration,
    AgentSharedState,
)
from naas_abi_core.services.agent.Agent_return_direct_test import _ScriptedChatModel
from naas_abi_core.services.agent.context import (
    agent_usable_module_scopes,
    process_scope_of,
    tool_scope_refused,
)
from naas_abi_core.utils.Expose import Expose

SCOPE = ("workflow", "acme.reports", "workflow.export_report")


class ExportReport(Expose):
    def __init__(self) -> None:
        self.ran: list[str] = []

    def run(self, quarter: str) -> str:
        self.ran.append(quarter)
        return f"exported {quarter}"

    def as_tools(self) -> list[BaseTool]:
        return [
            StructuredTool.from_function(
                func=self.run, name="export_report", description="Export a report."
            )
        ]


class LocalTool(Expose):
    """Not any module's workflow: an agent's own tool class."""

    def run(self, quarter: str) -> str:
        return quarter

    def as_tools(self) -> list[BaseTool]:
        return [
            StructuredTool.from_function(
                func=self.run, name="local", description="Local."
            )
        ]


@pytest.fixture
def workflow() -> ExportReport:
    """An instance the agent builds itself, as BodoAgent does with
    ``ExecutePythonCodeWorkflow(config)``: the module only declares the class."""
    module = SimpleNamespace(
        workflows=[], pipelines=[], workflow_classes=[ExportReport], pipeline_classes=[]
    )
    assert tag_process_scopes({"acme.reports": module}) == 1
    return ExportReport()


def _turn(workflow: ExportReport) -> str:
    agent = Agent(
        name="reports_agent",
        description="Exports reports",
        chat_model=_ScriptedChatModel(
            script=[
                AIMessage(
                    content="",
                    tool_calls=[
                        {"name": "export_report", "args": {"quarter": "q3"}, "id": "c1"}
                    ],
                ),
                AIMessage(content="done"),
            ]
        ),
        tools=[*workflow.as_tools()],
        agents=[],
        memory=MemorySaver(),
        state=AgentSharedState(thread_id="module-scope-tools"),
        configuration=AgentConfiguration(system_prompt="You are under test."),
        enable_default_tools=False,
    )
    seen: list[Any] = []
    for event in agent.stream_invoke("export q3"):
        seen.append(event.get("data"))
    return "\n".join(str(s) for s in seen)


def test_an_engine_workflow_class_has_its_module_scope(workflow) -> None:
    assert process_scope_of(workflow) == SCOPE
    (tool,) = workflow.as_tools()
    assert tool_scope_refused(tool) is None  # an unbound turn
    token = agent_usable_module_scopes.set(frozenset())
    try:
        assert tool_scope_refused(tool) == SCOPE
        agent_usable_module_scopes.set(frozenset({SCOPE}))
        assert tool_scope_refused(tool) is None
    finally:
        agent_usable_module_scopes.reset(token)


def test_an_agent_refuses_a_workflow_the_caller_may_not_run(workflow) -> None:
    token = agent_usable_module_scopes.set(frozenset())
    try:
        reply = _turn(workflow)
    finally:
        agent_usable_module_scopes.reset(token)
    assert workflow.ran == []
    assert "You may not run the workflow workflow.export_report" in reply


def test_an_agent_runs_a_workflow_the_caller_may_run(workflow) -> None:
    token = agent_usable_module_scopes.set(frozenset({SCOPE}))
    try:
        _turn(workflow)
    finally:
        agent_usable_module_scopes.reset(token)
    assert workflow.ran == ["q3"]


def test_a_subclass_of_a_module_workflow_is_bounded_like_it(workflow) -> None:
    class Narrower(ExportReport):
        pass

    (tool,) = Narrower().as_tools()
    token = agent_usable_module_scopes.set(frozenset())
    try:
        assert tool_scope_refused(tool) == SCOPE
    finally:
        agent_usable_module_scopes.reset(token)


def test_a_class_two_modules_declare_keeps_the_first_scope(workflow) -> None:
    other = SimpleNamespace(
        workflows=[], pipelines=[], workflow_classes=[ExportReport], pipeline_classes=[]
    )
    assert tag_process_scopes({"acme.other": other}) == 0
    assert process_scope_of(ExportReport()) == SCOPE


def test_a_tool_of_no_module_workflow_is_not_bounded() -> None:
    (tool,) = LocalTool().as_tools()
    token = agent_usable_module_scopes.set(frozenset())
    try:
        assert tool_scope_refused(tool) is None
    finally:
        agent_usable_module_scopes.reset(token)
