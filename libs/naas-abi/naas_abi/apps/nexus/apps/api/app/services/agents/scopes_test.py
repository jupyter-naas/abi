"""An engine module's workflows and pipelines, as agents' tools: a turn binds
the ones the caller may run in its workspace."""

from __future__ import annotations

import pytest
from naas_abi.apps.nexus.apps.api.app.core.agent_feature_access import bind_usable_processes
from naas_abi.apps.nexus.apps.api.app.services.agents import scopes
from naas_abi.apps.nexus.apps.api.app.services.iam.authz import ModuleScope
from naas_abi_core.services.agent.context import agent_usable_module_scopes

EXPORT = ModuleScope("workflow", "acme.reports", "workflow.export")
DAILY = ModuleScope("pipeline", "acme.reports", "pipeline.daily")


@pytest.fixture(autouse=True)
def processes(monkeypatch):
    monkeypatch.setattr(scopes, "engine_process_scopes", lambda: [EXPORT, DAILY])


@pytest.mark.asyncio
async def test_a_turn_binds_the_workflows_the_caller_may_run(team) -> None:
    assert await scopes.usable_process_scopes("member", "ws-1") == frozenset()
    assert await scopes.usable_process_scopes("admin", "ws-1") == {
        ("workflow", "acme.reports", "workflow.export"),
        ("pipeline", "acme.reports", "pipeline.daily"),
    }
    team.allow_scope("member", EXPORT, "abi:org-1:ws-1")
    assert await scopes.usable_process_scopes("member", "ws-1") == {
        ("workflow", "acme.reports", "workflow.export")
    }


@pytest.mark.asyncio
async def test_a_turn_without_a_workspace_runs_no_module_workflow(team) -> None:
    token = agent_usable_module_scopes.set(None)
    try:
        await bind_usable_processes("admin", None)
        assert agent_usable_module_scopes.get() == frozenset()
        await bind_usable_processes("admin", "ws-1")
        assert len(agent_usable_module_scopes.get() or ()) == 2
    finally:
        agent_usable_module_scopes.reset(token)
