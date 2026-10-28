"""``WorkspaceVisibility`` and each kind's reader: what a workspace turned off."""

from __future__ import annotations

from types import SimpleNamespace

import pytest
from naas_abi.apps.nexus.apps.api.app.services.agents.visibility import AgentsVisibility
from naas_abi.apps.nexus.apps.api.app.services.apps.visibility import AppsVisibility
from naas_abi.apps.nexus.apps.api.app.services.iam.authz import ModuleScope
from naas_abi.apps.nexus.apps.api.app.services.visibility.port import VisibilityReaderPort
from naas_abi.apps.nexus.apps.api.app.services.visibility.service import WorkspaceVisibility
from naas_abi.apps.nexus.apps.api.app.services.workflows.adapters.secondary.in_memory import (
    InMemoryWorkflowVisibility,
)
from naas_abi.apps.nexus.apps.api.app.services.workflows.port import WorkflowSwitch
from naas_abi.apps.nexus.apps.api.app.services.workflows.visibility import WorkflowsVisibility

MAP = ModuleScope("app", "acme.ops", "map")
CHART = ModuleScope("app", "acme.ops", "chart")
CONSOLE = ModuleScope("app", "acme.research", "console")


def _apps(states: dict[str, bool], seeded: set[str] = frozenset()) -> AppsVisibility:
    async def stored(workspace_id: str) -> dict[str, bool]:
        return states if workspace_id == "ws-1" else {}

    async def seed(workspace_id: str) -> set[str]:
        return set(seeded) if workspace_id == "ws-1" else set()

    return AppsVisibility(stored, seed)


@pytest.mark.asyncio
async def test_an_app_is_on_by_its_row_else_its_seed_else_off() -> None:
    apps = _apps(
        {"acme.ops:map": True, "acme.ops:chart": False, "remote/acme.research:console": True},
        seeded={"acme.ops:chart", "acme.ops:table"},
    )
    table = ModuleScope("app", "acme.ops", "table")
    other = ModuleScope("app", "acme.ops", "other")
    # The row wins over the seed (chart); the seed turns on what has no row (table);
    # a remote app's id names its module; nothing at all is off.
    assert await apps.hidden("ws-1", [MAP, CHART, CONSOLE, table, other]) == {CHART, other}
    assert await apps.hidden("ws-2", [MAP]) == {MAP}


@pytest.mark.asyncio
async def test_a_module_agent_is_hidden_when_its_rows_are_off_and_unknown_ones_are_not() -> None:
    rows = [
        SimpleNamespace(class_name="acme.people/Recruiter", provider="abi", enabled=False),
        SimpleNamespace(class_name="acme.people/Scout", provider="abi", enabled=True),
    ]

    async def stored(workspace_id: str) -> list[SimpleNamespace]:
        return rows

    def resolver():
        return lambda row: ModuleScope("agent", "acme.people", row.class_name.split("/")[1])

    agents = AgentsVisibility(stored, resolver)
    recruiter = ModuleScope("agent", "acme.people", "Recruiter")
    scout = ModuleScope("agent", "acme.people", "Scout")
    absent = ModuleScope("agent", "acme.people", "Absent")
    assert await agents.hidden("ws-1", [recruiter, scout, absent]) == {recruiter}


@pytest.mark.asyncio
async def test_a_workflow_is_on_until_switched_off_in_its_workspace() -> None:
    store = InMemoryWorkflowVisibility()
    tweets = ModuleScope("workflow", "acme.tweets", "tweets")
    nightly = ModuleScope("pipeline", "acme.tweets", "pipeline.nightly")
    workflows = WorkflowsVisibility(store)
    assert await workflows.hidden("ws-1", [tweets, nightly]) == set()
    await store.put(WorkflowSwitch("ws-1", "workflow", "acme.tweets", "tweets", False))
    await store.put(WorkflowSwitch("ws-1", "pipeline", "acme.tweets", "pipeline.nightly", True))
    assert await workflows.hidden("ws-1", [tweets, nightly]) == {tweets}
    assert await workflows.hidden("ws-2", [tweets]) == set()
    await store.put(WorkflowSwitch("ws-1", "workflow", "acme.tweets", "tweets", True))
    assert await workflows.hidden("ws-1", [tweets]) == set()


class _Broken(VisibilityReaderPort):
    async def hidden(self, workspace_id, scopes):
        raise RuntimeError("database down")


@pytest.mark.asyncio
async def test_each_kind_asks_its_reader_and_a_failed_read_hides() -> None:
    visibility = WorkspaceVisibility({"app": _apps({"acme.ops:map": True}), "agent": _Broken()})
    agent = ModuleScope("agent", "acme.people", "Recruiter")
    workflow = ModuleScope("workflow", "acme.tweets", "tweets")
    # No reader for workflows here: nothing of them is hidden.
    assert await visibility.hidden("ws-1", [MAP, CHART, agent, workflow]) == {CHART, agent}
    assert await visibility.is_hidden("ws-1", MAP) is False
