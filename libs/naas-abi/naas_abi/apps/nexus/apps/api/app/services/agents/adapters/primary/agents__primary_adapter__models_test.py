"""The agents a workspace lists, kept to the models it uses (``iam/workspace_models``):
the picker offers those of an agent's models the workspace uses, else its default, and
an agent on a model it does not offer is shown on the default it switches to."""

from __future__ import annotations

from datetime import datetime

from naas_abi.apps.nexus.apps.api.app.services.agents.adapters.primary.agents__primary_adapter__FastAPI import (  # noqa: E501
    kept_to_models,
)
from naas_abi.apps.nexus.apps.api.app.services.agents.port import AgentRecord
from naas_abi.apps.nexus.apps.api.app.services.iam.workspace_models import (
    UNRESTRICTED,
    WorkspaceModels,
)

NOW = datetime(2026, 11, 26)


def _agent(resolved: str | None, model_ids: list[str] | None) -> AgentRecord:
    return AgentRecord(
        id="a",
        workspace_id="w",
        name="A",
        description="",
        class_name="m/A",
        module_path="m",
        system_prompt=None,
        model_id=None,
        provider=None,
        logo_url=None,
        created_at=NOW,
        updated_at=NOW,
        resolved_model_id=resolved,
        model_ids=model_ids,
    )


def test_an_agent_is_listed_with_the_models_its_workspace_uses():
    limited = WorkspaceModels(frozenset({"qwen-3.8", "gpt-x"}), "qwen-3.8")
    kept = kept_to_models(_agent("gpt-y", ["gpt-y", "gpt-x"]), limited)
    assert kept.model_ids == ["gpt-x"] and kept.resolved_model_id == "qwen-3.8"
    none_offered = kept_to_models(_agent("gpt-y", ["gpt-y"]), limited)
    assert none_offered.model_ids == ["qwen-3.8"]
    offered = kept_to_models(_agent("gpt-x", None), limited)
    assert offered.resolved_model_id == "gpt-x" and offered.model_ids is None
    agent = _agent("gpt-y", ["gpt-y"])
    assert kept_to_models(agent, UNRESTRICTED) is agent
    no_default = kept_to_models(_agent("gpt-y", None), WorkspaceModels(frozenset({"x"}), None))
    assert no_default.resolved_model_id is None
