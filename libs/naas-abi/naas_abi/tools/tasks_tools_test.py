from __future__ import annotations

import asyncio
from datetime import date, datetime
from types import SimpleNamespace
from typing import Any

import pytest

from naas_abi.agents.feature.context import nexus_feature_context
from naas_abi.apps.nexus.apps.api.app.services.tasks.adapters.secondary.memory import (
    InMemoryTasksMemberDirectory,
    InMemoryTasksStore,
)
from naas_abi.apps.nexus.apps.api.app.services.tasks.service import TasksService
from naas_abi.tools import tasks_tools as tools_module

WS = "ws-1"
ADA = "u-ada"
GRACE = "u-grace"
TODAY = date(2026, 10, 22)


def _member(user_id: str, name: str, role: str) -> SimpleNamespace:
    return SimpleNamespace(
        user_id=user_id, name=name, email=f"{name.lower()}@acme.io", role=role
    )


@pytest.fixture
def tasks(monkeypatch) -> dict[str, Any]:
    ticks = iter(range(10_000))
    service = TasksService(
        InMemoryTasksStore(),
        InMemoryTasksMemberDirectory({WS: {ADA, GRACE}}),
        clock=lambda: datetime(2026, 10, 22, 9, next(ticks) // 60, next(ticks) % 60),
    )
    state = {"user": ADA, "role": "owner"}
    members = [_member(ADA, "Ada", "owner"), _member(GRACE, "Grace", "member")]

    def execute(op):
        call = tools_module.TasksCall(
            service=service,
            workspace_id=WS,
            user_id=state["user"],
            role=state["role"],
            members=members,
            today=TODAY,
        )
        return asyncio.run(op(call))

    monkeypatch.setattr(tools_module, "_execute", execute)
    by_name = {t.name: t for t in tools_module.tasks_tools()}
    return {"tools": by_name, "service": service, "state": state}


def _run(tasks: dict[str, Any], name: str, **args: Any) -> Any:
    return tasks["tools"][name].invoke(args)


def test_create_list_and_update_by_names(tasks):
    created = _run(
        tasks,
        "create_task",
        title="Write the spec",
        assignees=["Grace"],
        priority="High",
    )
    row = created["created"]
    assert (row["scope"], row["stage"], row["priority"], row["assignees"]) == (
        "current",
        "Ready",
        "High",
        ["Grace"],
    )

    updated = _run(
        tasks,
        "update_task",
        task="write the spec",
        stage="Review",
        add_assignees=["me"],
        add_labels=["Data"],
        github_issue_url="https://github.com/acme/abi/issues/9",
    )["updated"]
    assert updated["stage"] == "Review"
    assert updated["assignees"] == ["Grace", "Ada"]
    assert updated["labels"] == ["Data"]
    assert updated["github_issue_url"] == "https://github.com/acme/abi/issues/9"

    listed = _run(tasks, "list_tasks", scope="current", assignee="ada@acme.io")
    assert [t["title"] for t in listed["tasks"]] == ["Write the spec"]


def test_inbox_backlog_and_moving_between_scopes(tasks):
    _run(tasks, "create_task", title="Request", scope="inbox")
    _run(tasks, "create_task", title="Later", scope="backlog")
    assert [t["title"] for t in _run(tasks, "list_tasks", scope="inbox")["tasks"]] == [
        "Request"
    ]

    moved = _run(tasks, "update_task", task="Request", scope="next")["updated"]

    assert (moved["scope"], moved["stage"]) == ("next", "Ready")
    assert [
        t["title"] for t in _run(tasks, "list_tasks", scope="backlog")["tasks"]
    ] == ["Later"]


def test_tools_default_to_the_open_task(tasks):
    task_id = _run(tasks, "create_task", title="Open one")["created"]["id"]
    token = nexus_feature_context.set(
        {"key": "tasks", "resource": {"kind": "task", "id": task_id}}
    )
    try:
        _run(tasks, "add_task_comment", body="Looks good")
        assert _run(tasks, "get_task")["comments"][0]["body"] == "Looks good"
    finally:
        nexus_feature_context.reset(token)


def test_comment_reply_and_removal_rules(tasks):
    _run(tasks, "create_task", title="T")
    root = _run(tasks, "add_task_comment", task="T", body="Question")["commented"][
        "comment_id"
    ]
    reply = _run(tasks, "add_task_comment", task="T", body="Answer", reply_to=root)[
        "commented"
    ]
    assert reply["reply_to"] == root
    assert [
        r["body"] for r in _run(tasks, "get_task", task="T")["comments"][0]["replies"]
    ] == ["Answer"]

    # Grace, a member, cannot remove Ada's comment.
    tasks["state"].update(user=GRACE, role="member")
    refused = _run(tasks, "delete_task_comment", task="T", comment_id=root)
    assert "error" in refused

    tasks["state"].update(user=ADA, role="owner")
    assert "removed" in _run(tasks, "delete_task_comment", task="T", comment_id=root)
    assert _run(tasks, "get_task", task="T")["comments"] == []


def test_delete_needs_confirmation_and_keeps_history(tasks):
    _run(tasks, "create_task", title="Doomed")

    asked = _run(tasks, "delete_task", task="Doomed")
    assert "needs_confirmation" in asked
    assert _run(tasks, "list_tasks")["total"] == 1

    assert (
        _run(tasks, "delete_task", task="Doomed", confirm=True)["deleted"]["title"]
        == "Doomed"
    )
    events = _run(tasks, "get_tasks_activity")["events"]
    assert (events[0]["event"], events[0]["task"]) == ("deleted", "Doomed")


def test_unknown_names_are_explained_not_guessed(tasks):
    assert (
        "Use one of" in _run(tasks, "create_task", title="T", stage="Shipping")["error"]
    )
    assert (
        "list_task_members"
        in _run(tasks, "create_task", title="T", assignees=["Linus"])["error"]
    )
    _run(tasks, "create_task", title="Spec A")
    _run(tasks, "create_task", title="Spec B")
    assert (
        "Several tasks match"
        in _run(tasks, "update_task", task="spec", stage="Done")["error"]
    )


def test_only_owners_and_admins_change_settings(tasks):
    tasks["state"].update(user=GRACE, role="member")
    assert "error" in _run(tasks, "update_tasks_settings", feed_limit=10)
    assert _run(tasks, "get_tasks_settings")["can_edit"] is False

    tasks["state"].update(user=ADA, role="admin")
    saved = _run(
        tasks, "update_tasks_settings", feed_limit=10, suggested_labels=["Ops"]
    )["saved"]
    assert (saved["feed_limit"], saved["suggested_labels"]) == (10, ["Ops"])


def test_carry_over_moves_unfinished_tasks(tasks):
    _run(tasks, "create_task", title="Unfinished")
    _run(tasks, "create_task", title="Finished", stage="Done")

    result = _run(tasks, "carry_over_unfinished_tasks")

    assert result["moved"] == ["Unfinished"]
    assert [t["title"] for t in _run(tasks, "list_tasks", scope="next")["tasks"]] == [
        "Unfinished"
    ]


def test_write_tools_are_real_tools_and_mirrored_by_the_web():
    from pathlib import Path

    from naas_abi.tools.nexus_source_tools import PACKAGE_ROOT

    names = {t.name for t in tools_module.tasks_tools()}
    assert set(tools_module.TASK_WRITE_TOOLS) <= names

    web = Path(PACKAGE_ROOT) / "apps/nexus/apps/web/src/stores/tasks.ts"
    if not web.is_file():
        pytest.skip("web sources not shipped")
    block = web.read_text(encoding="utf-8").split("TASK_WRITE_TOOLS = [", 1)[1]
    listed = {
        line.strip().strip("',")
        for line in block.split("]", 1)[0].splitlines()
        if line.strip().strip("',")
    }
    assert listed == set(tools_module.TASK_WRITE_TOOLS)
