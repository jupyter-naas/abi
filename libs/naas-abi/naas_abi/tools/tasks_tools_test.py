"""The Tasks agent's tools, decided by IAM as ``/api/tasks`` is.

A real IAM: Ada owns ``ws-1``, Grace and Vera are its member and viewer, Sam
belongs to nothing. The deployment's feature defaults give ``tasks`` to owners
and admins only. Each tool opens the call the real way (``_open_call``) on the
in-memory service.
"""

from __future__ import annotations

import asyncio
from dataclasses import replace
from datetime import date, datetime
from types import SimpleNamespace
from typing import Any

import pytest
from naas_abi_core.engine.call_context import use_call_context

from naas_abi.agents.feature.context import nexus_feature_context
from naas_abi.apps.nexus.apps.api.app.services.iam.names import workspace_scope
from naas_abi.apps.nexus.apps.api.app.services.iam.testing import NexusIam
from naas_abi.apps.nexus.apps.api.app.services.tasks.adapters.secondary.memory import (
    InMemoryTasksMemberDirectory,
    InMemoryTasksStore,
)
from naas_abi.apps.nexus.apps.api.app.services.tasks.service import TasksService
from naas_abi.tools import tasks_tools as tools_module

WS = "ws-1"
ADA = "u-ada"
GRACE = "u-grace"
VERA = "u-vera"
SAM = "u-sam"
TODAY = date(2026, 10, 22)
# What a personal key limited to reading carries (its ``abi_scope``).
READ_ONLY_KEY = (
    {
        "effect": "Allow",
        "actions": ["nexus:UseFeature", "nexus:List*", "nexus:Get*"],
        "resources": ["*"],
    },
)


def _member(user_id: str, name: str, role: str) -> SimpleNamespace:
    return SimpleNamespace(
        user_id=user_id, name=name, email=f"{name.lower()}@acme.io", role=role
    )


@pytest.fixture
def tasks(monkeypatch) -> Any:
    ticks = iter(range(10_000))
    service = TasksService(
        InMemoryTasksStore(),
        InMemoryTasksMemberDirectory({WS: {ADA, GRACE, VERA}}),
        clock=lambda: datetime(2026, 10, 22, 9, next(ticks) // 60, next(ticks) % 60),
    )
    state = {"user": ADA}
    members = [
        _member(ADA, "Ada", "owner"),
        _member(GRACE, "Grace", "member"),
        _member(VERA, "Vera", "viewer"),
    ]

    async def board(db: Any, workspace_id: str) -> tuple[Any, list[Any]]:
        return service, members

    monkeypatch.setattr(tools_module, "tool_context", lambda: (state["user"], WS))
    monkeypatch.setattr(tools_module, "run_db", lambda fn: asyncio.run(fn(None)))
    monkeypatch.setattr(tools_module, "_board", board)
    monkeypatch.setattr(tools_module, "_today", lambda: TODAY)

    nexus = NexusIam()
    scope = nexus.workspace("org-1", WS)
    for user, role in ((ADA, "owner"), (GRACE, "member"), (VERA, "viewer")):
        nexus.grant(user, role, scope)
    nexus.user(SAM)
    nexus.platform_admin("root")
    by_name = {t.name: t for t in tools_module.tasks_tools()}
    with nexus.installed():
        yield {"tools": by_name, "service": service, "state": state, "iam": nexus}


def _grant_tasks(tasks: dict[str, Any], user: str) -> None:
    tasks["iam"].allow(
        user,
        ["nexus:UseFeature"],
        ["${scope}:nexus:feature/tasks"],
        workspace_scope("org-1", WS),
    )


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

    # Grace, a member given Tasks, cannot remove Ada's comment.
    _grant_tasks(tasks, GRACE)
    tasks["state"].update(user=GRACE)
    refused = _run(tasks, "delete_task_comment", task="T", comment_id=root)
    assert "error" in refused

    tasks["state"].update(user=ADA)
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
    _grant_tasks(tasks, GRACE)
    tasks["state"].update(user=GRACE)
    assert "error" in _run(tasks, "update_tasks_settings", feed_limit=10)
    assert _run(tasks, "get_tasks_settings")["can_edit"] is False

    tasks["state"].update(user=ADA)
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


NOT_ENABLED = "This feature is not available to you in this workspace"


@pytest.mark.parametrize("user", [GRACE, VERA])
def test_members_and_viewers_are_refused_by_default(tasks, user):
    tasks["state"].update(user=user)

    assert _run(tasks, "list_tasks") == {"error": NOT_ENABLED}
    assert _run(tasks, "create_task", title="T") == {"error": NOT_ENABLED}


def test_a_stranger_is_refused(tasks):
    tasks["state"].update(user=SAM)

    assert _run(tasks, "list_tasks") == {
        "error": "You do not have access to this workspace"
    }


def test_a_member_given_the_feature_works_on_tasks_and_removes_only_their_comments(
    tasks,
):
    _run(tasks, "create_task", title="T")
    adas = _run(tasks, "add_task_comment", task="T", body="Ada's")["commented"]
    _grant_tasks(tasks, GRACE)
    tasks["state"].update(user=GRACE)

    assert "created" in _run(tasks, "create_task", title="Grace's")
    graces = _run(tasks, "add_task_comment", task="T", body="Grace's")["commented"]
    assert "removed" in _run(
        tasks, "delete_task_comment", task="T", comment_id=graces["comment_id"]
    )
    assert "error" in _run(
        tasks, "delete_task_comment", task="T", comment_id=adas["comment_id"]
    )


def test_a_viewer_given_the_feature_reads_and_writes_nothing(tasks):
    _run(tasks, "create_task", title="T")
    _grant_tasks(tasks, VERA)
    tasks["state"].update(user=VERA)

    assert _run(tasks, "list_tasks")["total"] == 1
    assert _run(tasks, "get_task", task="T")["title"] == "T"
    assert "events" in _run(tasks, "get_tasks_activity")
    for name, args in (
        ("create_task", {"title": "No"}),
        ("update_task", {"task": "T", "title": "No"}),
        ("archive_task", {"task": "T"}),
        ("delete_task", {"task": "T", "confirm": True}),
        ("add_task_comment", {"task": "T", "body": "No"}),
        ("carry_over_unfinished_tasks", {}),
    ):
        assert "error" in _run(tasks, name, **args), name
    assert _run(tasks, "list_tasks")["tasks"][0]["title"] == "T"


def test_a_workspace_without_tasks_in_its_set_refuses_all_but_the_platform_admin(
    tasks,
):
    tasks["iam"].put_set("org-1", WS, features=["chat", "settings"])

    assert _run(tasks, "list_tasks") == {"error": NOT_ENABLED}
    tasks["state"].update(user="root")
    assert "created" in _run(tasks, "create_task", title="T")


def test_a_read_only_key_reads_and_cannot_write(tasks):
    _run(tasks, "create_task", title="T")
    narrowed = replace(NexusIam.context(ADA), scope=READ_ONLY_KEY)

    with use_call_context(narrowed):
        assert _run(tasks, "list_tasks")["total"] == 1
        assert _run(tasks, "get_tasks_settings")["can_edit"] is False
        assert "error" in _run(tasks, "create_task", title="No")
        assert "error" in _run(tasks, "update_tasks_settings", feed_limit=10)
    assert "created" in _run(tasks, "create_task", title="Yes")
