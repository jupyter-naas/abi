import json
import sys
from pathlib import Path
from types import ModuleType
from unittest.mock import MagicMock, patch

import pytest
from naas_abi_core.services.agent.IntentAgent import IntentType

from naas_abi_marketplace.domains.support.agents.SupportAgent import (
    INTENTS_FILE,
    SupportAgent,
)


@pytest.fixture
def agent() -> SupportAgent:
    from naas_abi_core.engine.Engine import Engine

    engine = Engine()
    engine.load(module_names=["naas_abi_marketplace.domains.support"])

    return SupportAgent.New()


def test_get_intents_parses_raw_agent_tool(tmp_path: Path) -> None:
    path = tmp_path / "intents.json"
    payload = [
        {
            "intent_type": "RAW",
            "intent_value": "raw message",
            "intent_target": "raw-target",
        },
        {
            "intent_type": "AGENT",
            "intent_value": "agent message",
            "intent_target": "OtherAgent",
        },
        {
            "intent_type": "TOOL",
            "intent_value": "tool message",
            "intent_target": "some_tool",
        },
    ]
    path.write_text(json.dumps(payload), encoding="utf-8")

    intents = SupportAgent.get_intents(path)

    assert len(intents) == 3
    assert intents[0].intent_type == IntentType.RAW
    assert intents[0].intent_value == "raw message"
    assert intents[1].intent_type == IntentType.AGENT
    assert intents[2].intent_type == IntentType.TOOL


def test_get_intents_unknown_intent_type_raises(tmp_path: Path) -> None:
    path = tmp_path / "bad.json"
    path.write_text(
        json.dumps(
            [
                {
                    "intent_type": "UNKNOWN",
                    "intent_value": "x",
                    "intent_target": "y",
                }
            ]
        ),
        encoding="utf-8",
    )

    with pytest.raises(ValueError, match="Unknown intent_type"):
        SupportAgent.get_intents(path)


def test_support_agent_intents_match_json_file() -> None:
    raw = json.loads(INTENTS_FILE.read_text(encoding="utf-8"))
    assert len(SupportAgent.intents) == len(raw)
    for loaded, row in zip(SupportAgent.intents, raw, strict=True):
        assert loaded.intent_value == row["intent_value"]
        assert loaded.intent_target == row["intent_target"]
        assert loaded.intent_type.name == row["intent_type"]


def test_build_system_prompt_substitutes_repository_project_and_tools() -> None:
    class _Tool:
        def __init__(self, name: str, description: str) -> None:
            self.name = name
            self.description = description

    tools = [
        _Tool("github_list_issues", "List issues."),
        _Tool("support_bug_report", "File a bug."),
    ]
    prompt = SupportAgent.build_system_prompt(
        github_repository="org/repo",
        github_project_id=42,
        tools=tools,
    )

    assert "org/repo" in prompt
    assert "42" in prompt
    assert "- github_list_issues: List issues." in prompt
    assert "- support_bug_report: File a bug." in prompt
    assert "[TOOLS]" not in prompt
    assert "[GITHUB_REPOSITORY]" not in prompt
    assert "[GITHUB_PROJECT_ID]" not in prompt


def test_get_tools_filters_allowlisted_github_tools_and_appends_workflows(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Avoid importing real workflow modules (they require ABIModule at import time)."""

    def mk_tool(name: str) -> MagicMock:
        t = MagicMock()
        t.name = name
        t.description = "d"
        return t

    rest_tools = [
        mk_tool("github_list_issues"),
        mk_tool("github_delete_repository"),
        mk_tool("github_get_issue"),
    ]
    gql_tools = [
        mk_tool("githubgraphql_list_priorities"),
        mk_tool("githubgraphql_other"),
    ]

    rb_mod = ModuleType(
        "naas_abi_marketplace.domains.support.workflows.ReportBugWorkflow"
    )

    class _FakeReportBugWorkflow:
        def __init__(self, *args: object, **kwargs: object) -> None:
            pass

        def as_tools(self) -> list:
            return [mk_tool("support_bug_report")]

    rb_mod.ReportBugWorkflow = _FakeReportBugWorkflow
    rb_mod.ReportBugWorkflowConfiguration = MagicMock

    fr_mod = ModuleType(
        "naas_abi_marketplace.domains.support.workflows.FeatureRequestWorkflow"
    )

    class _FakeFeatureRequestWorkflow:
        def __init__(self, *args: object, **kwargs: object) -> None:
            pass

        def as_tools(self) -> list:
            return [mk_tool("support_feature_request")]

    fr_mod.FeatureRequestWorkflow = _FakeFeatureRequestWorkflow
    fr_mod.FeatureRequestWorkflowConfiguration = MagicMock

    rb_name = "naas_abi_marketplace.domains.support.workflows.ReportBugWorkflow"
    fr_name = "naas_abi_marketplace.domains.support.workflows.FeatureRequestWorkflow"
    monkeypatch.setitem(sys.modules, rb_name, rb_mod)
    monkeypatch.setitem(sys.modules, fr_name, fr_mod)

    with (
        patch(
            "naas_abi_marketplace.applications.github.integrations.GitHubIntegration.as_tools",
            return_value=rest_tools,
        ),
        patch(
            "naas_abi_marketplace.applications.github.integrations.GitHubGraphqlIntegration.as_tools",
            return_value=gql_tools,
        ),
    ):
        tools = SupportAgent.get_tools("fake-token")

    names = [t.name for t in tools]
    assert "github_list_issues" in names
    assert "github_get_issue" in names
    assert "github_delete_repository" not in names
    assert "githubgraphql_list_priorities" in names
    assert "githubgraphql_other" not in names
    assert "support_bug_report" in names
    assert "support_feature_request" in names


def test_support_agent_static_identity() -> None:
    assert SupportAgent.name == "Support"
    assert "GitHub" in SupportAgent.description
    assert SupportAgent.model == "gpt-4.1-mini"
    assert len(SupportAgent.suggestions) == 2
    labels = {s["label"] for s in SupportAgent.suggestions}
    assert "Feature Request" in labels
    assert "Report Bug" in labels


def test_create_bug_report(agent: SupportAgent) -> None:
    result = agent.invoke(
        "Create a bug report on the topic: Impossible to make chat with agent"
    )

    assert result is not None, f"Result is None: {result}"


def test_create_feature_request(agent: SupportAgent) -> None:
    result = agent.invoke(
        "Create a feature request on the topic: Add integration with Github to core modules"
    )

    assert result is not None, f"Result is None: {result}"


def test_list_and_inspect_issues_use_case(agent: SupportAgent) -> None:
    """Covers list/get issue flows described in SupportAgent system prompt."""
    result = agent.invoke(
        "List open issues in the default repository and summarize titles only."
    )
    assert result is not None, f"Result is None: {result}"


def test_repository_contributors_use_case(agent: SupportAgent) -> None:
    """Aligns with SupportAgentIntents.json TOOL intent for contributors."""
    result = agent.invoke("Who are the contributors of the repository?")
    assert result is not None, f"Result is None: {result}"


def test_declared_intents_return_results(agent: SupportAgent) -> None:
    """Each intent from SupportAgentIntents.json should produce a non-empty reply."""
    for intent in agent.intents:
        result = agent.invoke(intent.intent_value)
        assert result is not None, f"Intent {intent.intent_value!r} returned None"
