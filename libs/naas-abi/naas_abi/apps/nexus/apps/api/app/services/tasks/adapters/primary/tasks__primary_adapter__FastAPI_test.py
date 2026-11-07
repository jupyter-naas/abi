from __future__ import annotations

import asyncio
from contextlib import ExitStack
from types import SimpleNamespace

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from naas_abi.apps.nexus.apps.api.app.services.auth.adapters.primary import (
    auth__primary_adapter__dependencies as auth_dependencies,
)
from naas_abi.apps.nexus.apps.api.app.services.iam.testing import NexusIam
from naas_abi.apps.nexus.apps.api.app.services.tasks.adapters.primary import (
    tasks__primary_adapter__FastAPI as api,
)
from naas_abi.apps.nexus.apps.api.app.services.tasks.adapters.secondary.memory import (
    InMemoryTasksMemberDirectory,
    InMemoryTasksStore,
)
from naas_abi.apps.nexus.apps.api.app.services.tasks.service import TasksService

WS = "ws-1"
OTHER_WS = "ws-2"
USER = "u-1"


@pytest.fixture
def client_for():
    service = TasksService(
        InMemoryTasksStore(), InMemoryTasksMemberDirectory({WS: {USER, "u-2"}, OTHER_WS: {USER}})
    )
    stack = ExitStack()

    def make(role: str | None, *, tasks: bool = True) -> TestClient:
        """The caller holds ``role`` in both workspaces (None: no role there)
        and, with ``tasks``, a policy granting the feature: no role brings it."""
        nexus = NexusIam(features_with_roles=False)
        nexus.user(USER)
        for workspace in (WS, OTHER_WS):
            scope = nexus.workspace("org-1", workspace)
            if role is not None:
                nexus.grant(USER, role, scope)
                if tasks:
                    nexus.give_features(nexus.principal(USER), ["tasks"], scope)
        stack.enter_context(nexus.installed())  # the latest client's world is the module's
        app = FastAPI()
        app.include_router(api.router, prefix="/api/tasks")
        caller = SimpleNamespace(id=USER)
        app.dependency_overrides[api.get_current_user_required] = lambda: caller
        app.dependency_overrides[auth_dependencies.get_current_user_required] = lambda: caller
        app.dependency_overrides[api.get_tasks_service] = lambda: service
        return TestClient(app)

    # Lets a test add records as another user than the caller.
    make.service = service  # type: ignore[attr-defined]
    with stack:
        yield make


@pytest.mark.parametrize("role", ["owner", "admin"])
def test_owners_and_admins_use_tasks(client_for, role):
    client = client_for(role)

    res = client.post(f"/api/tasks/iterations?workspace_id={WS}", json={"date": "2026-10-22"})

    assert res.status_code == 200
    assert res.json()["start_date"] == "2026-10-19"
    assert res.json()["end_date"] == "2026-10-25"
    assert res.json()["iso_week"] == "2026-W43"


@pytest.mark.parametrize("role", ["owner", "admin", "member", "viewer"])
def test_no_role_brings_tasks(client_for, role):
    client = client_for(role, tasks=False)

    assert client.get(f"/api/tasks/iterations?workspace_id={WS}").status_code == 403
    assert client.post(f"/api/tasks?workspace_id={WS}", json={"title": "T"}).status_code == 403


def test_a_policy_granting_tasks_opens_them_to_a_member(client_for):
    client = client_for("member")

    assert client.get(f"/api/tasks/iterations?workspace_id={WS}").status_code == 200


def test_a_viewer_granted_tasks_reads_and_changes_nothing(client_for):
    client = client_for("viewer")

    assert client.get(f"/api/tasks/iterations?workspace_id={WS}").status_code == 200
    assert client.post(f"/api/tasks?workspace_id={WS}", json={"title": "T"}).status_code == 403


def test_outsiders_are_refused(client_for):
    client = client_for(None)

    assert client.get(f"/api/tasks/iterations?workspace_id={WS}").status_code == 403


def test_task_lifecycle_over_http(client_for):
    client = client_for("admin")
    iteration = client.post(
        f"/api/tasks/iterations?workspace_id={WS}", json={"date": "2026-10-22"}
    ).json()

    created = client.post(
        f"/api/tasks?workspace_id={WS}",
        json={"title": "Write spec", "iteration_id": iteration["id"], "labels": ["Feature"]},
    )
    assert created.status_code == 201
    task = created.json()
    # Created in an iteration without a stage: the settings' default stage.
    assert task["stage"] == "ready"
    assert task["created_by"] == USER

    patched = client.patch(
        f"/api/tasks/{task['id']}?workspace_id={WS}",
        json={"stage": "review", "assignee_ids": ["u-2"], "due_date": "2026-11-02"},
    )
    assert patched.status_code == 200
    assert patched.json()["stage"] == "review"
    assert patched.json()["assignee_ids"] == ["u-2"]
    assert patched.json()["due_date"] == "2026-11-02"
    # Fields not sent stay as they were.
    assert patched.json()["labels"] == ["Feature"]

    cleared = client.patch(f"/api/tasks/{task['id']}?workspace_id={WS}", json={"due_date": None})
    assert cleared.json()["due_date"] is None

    listed = client.get(f"/api/tasks?workspace_id={WS}&iteration_id={iteration['id']}").json()
    assert [t["id"] for t in listed] == [task["id"]]

    assert (
        client.post(
            f"/api/tasks/{task['id']}/comments?workspace_id={WS}", json={"body": "LGTM"}
        ).status_code
        == 201
    )
    comments = client.get(f"/api/tasks/{task['id']}/comments?workspace_id={WS}").json()
    assert [c["body"] for c in comments] == ["LGTM"]

    activity = client.get(f"/api/tasks/{task['id']}/activity?workspace_id={WS}").json()
    assert [a["field"] for a in activity] == [
        "created",
        "stage",
        "assignees",
        "due_date",
        "due_date",
        "comment_added",
    ]
    assert {a["task_title"] for a in activity} == {"Write spec"}

    archived = client.post(f"/api/tasks/{task['id']}/archive?workspace_id={WS}").json()
    assert archived["archived"] is True
    assert client.get(f"/api/tasks?workspace_id={WS}&iteration_id={iteration['id']}").json() == []
    restored = client.post(f"/api/tasks/{task['id']}/restore?workspace_id={WS}").json()
    assert restored["archived"] is False

    assert client.delete(f"/api/tasks/{task['id']}?workspace_id={WS}").status_code == 204
    assert client.delete(f"/api/tasks/{task['id']}?workspace_id={WS}").status_code == 404
    # The deletion stays in the workspace feed, under the task's title.
    feed = client.get(f"/api/tasks/feed?workspace_id={WS}").json()
    assert (feed[0]["field"], feed[0]["task_title"]) == ("deleted", "Write spec")


def test_comment_replies_and_removal_over_http(client_for):
    owner = client_for("owner")
    task = owner.post(f"/api/tasks?workspace_id={WS}", json={"title": "T"}).json()
    comments_url = f"/api/tasks/{task['id']}/comments?workspace_id={WS}"
    root = owner.post(comments_url, json={"body": "Question"}).json()
    reply = owner.post(comments_url, json={"body": "Answer", "parent_id": root["id"]}).json()
    assert reply["parent_id"] == root["id"]

    # A member (Tasks opened to members) cannot remove someone else's comment.
    other = asyncio.run(client_for.service.add_comment(WS, task["id"], "Theirs", user_id="u-2"))
    member = client_for("member")
    one = f"/api/tasks/{task['id']}/comments/{other.id}?workspace_id={WS}"
    assert member.delete(one).status_code == 403
    # Owners and admins moderate; removing a comment removes its replies.
    owner = client_for("owner")  # each client sets the role for the module
    assert owner.delete(one).status_code == 204
    root_url = f"/api/tasks/{task['id']}/comments/{root['id']}?workspace_id={WS}"
    assert owner.delete(root_url).status_code == 204
    assert owner.get(comments_url).json() == []
    assert owner.delete(root_url).status_code == 404


def test_feed_settings_over_http(client_for):
    client = client_for("owner")
    settings = client.get(f"/api/tasks/settings?workspace_id={WS}").json()
    assert settings["feed_enabled"] is True
    assert settings["feed_limit"] == 20
    assert "comment_removed" in settings["feed_events"]

    payload = {
        k: settings[k]
        for k in (
            "iteration_weeks",
            "iteration_start_day",
            "stages",
            "priorities",
            "default_stage",
            "suggested_labels",
        )
    }
    saved = client.put(
        f"/api/tasks/settings?workspace_id={WS}",
        json={**payload, "today": "2026-10-22", "feed_events": ["created"], "feed_limit": 5},
    )
    assert saved.status_code == 200
    assert (saved.json()["feed_events"], saved.json()["feed_limit"]) == (["created"], 5)
    # Left out of a later save, the feed settings stay.
    again = client.put(
        f"/api/tasks/settings?workspace_id={WS}", json={**payload, "today": "2026-10-22"}
    )
    assert again.json()["feed_events"] == ["created"]
    bad = client.put(
        f"/api/tasks/settings?workspace_id={WS}",
        json={**payload, "today": "2026-10-22", "feed_limit": 0},
    )
    assert bad.status_code == 422


def test_backlog_goal_and_carry_over_over_http(client_for):
    client = client_for("owner")
    iteration = client.post(
        f"/api/tasks/iterations?workspace_id={WS}", json={"date": "2026-10-22"}
    ).json()
    backlog = client.post(f"/api/tasks?workspace_id={WS}", json={"title": "Idea"}).json()
    open_task = client.post(
        f"/api/tasks?workspace_id={WS}",
        json={"title": "Open", "iteration_id": iteration["id"], "stage": "in_progress"},
    ).json()

    assert [t["id"] for t in client.get(f"/api/tasks?workspace_id={WS}&backlog=true").json()] == [
        backlog["id"]
    ]
    # Without a scope: every task of the workspace, newest first.
    assert [t["id"] for t in client.get(f"/api/tasks?workspace_id={WS}").json()] == [
        open_task["id"],
        backlog["id"],
    ]
    assert (
        client.get(
            f"/api/tasks?workspace_id={WS}&backlog=true&iteration_id={iteration['id']}"
        ).status_code
        == 422
    )

    goal = client.patch(
        f"/api/tasks/iterations/{iteration['id']}?workspace_id={WS}", json={"goal": "Ship it"}
    )
    assert goal.json()["goal"] == "Ship it"

    carried = client.post(f"/api/tasks/iterations/{iteration['id']}/carry-over?workspace_id={WS}")
    assert carried.status_code == 200
    body = carried.json()
    assert body["iteration"]["start_date"] == "2026-10-26"
    assert [t["id"] for t in body["moved"]] == [open_task["id"]]


def test_validation_and_workspace_isolation_over_http(client_for):
    client = client_for("admin")
    task = client.post(f"/api/tasks?workspace_id={WS}", json={"title": "T"}).json()

    assert (
        client.post(
            f"/api/tasks?workspace_id={WS}", json={"title": "T", "stage": "doing"}
        ).status_code
        == 422
    )
    assert (
        client.post(
            f"/api/tasks?workspace_id={WS}", json={"title": "T", "assignee_ids": ["u-x"]}
        ).status_code
        == 422
    )
    assert (
        client.patch(
            f"/api/tasks/{task['id']}?workspace_id={OTHER_WS}", json={"title": "x"}
        ).status_code
        == 404
    )
    assert client.get(f"/api/tasks?workspace_id={OTHER_WS}&backlog=true").json() == []
    assert client.get(f"/api/tasks?workspace_id={OTHER_WS}").json() == []


def test_settings_are_read_by_tasks_users_and_saved_by_owners_and_admins(client_for):
    admin = client_for("admin")
    settings = admin.get(f"/api/tasks/settings?workspace_id={WS}")
    assert settings.status_code == 200
    body = settings.json()
    assert body["can_edit"] is True
    assert [s["key"] for s in body["stages"]][0] == "inbox"

    payload = {
        key: body[key]
        for key in (
            "iteration_weeks",
            "iteration_start_day",
            "stages",
            "priorities",
            "default_stage",
            "suggested_labels",
        )
    }
    payload.update(iteration_weeks=2, suggested_labels=["Ops"], today="2026-10-22")
    saved = admin.put(f"/api/tasks/settings?workspace_id={WS}", json=payload)
    assert saved.status_code == 200
    assert saved.json()["iteration_weeks"] == 2
    assert saved.json()["suggested_labels"] == ["Ops"]

    payload["iteration_weeks"] = 9
    assert admin.put(f"/api/tasks/settings?workspace_id={WS}", json=payload).status_code == 422

    # A member Tasks was opened to can read but not change the settings.
    member = client_for("member")
    read = member.get(f"/api/tasks/settings?workspace_id={WS}")
    assert read.status_code == 200 and read.json()["can_edit"] is False
    assert member.put(f"/api/tasks/settings?workspace_id={WS}", json=payload).status_code == 403


def test_created_tasks_carry_the_route_workspace(client_for):
    client = client_for("owner")
    # A workspace_id in the body is ignored: the route's workspace is the one used.
    created = client.post(
        f"/api/tasks?workspace_id={WS}", json={"title": "Mine", "workspace_id": OTHER_WS}
    )
    assert created.status_code == 201
    task = created.json()
    assert task["workspace_id"] == WS

    listed = client.get(f"/api/tasks?workspace_id={WS}").json()
    assert [t["workspace_id"] for t in listed] == [WS]
    assert client.get(f"/api/tasks?workspace_id={OTHER_WS}").json() == []

    patched = client.patch(
        f"/api/tasks/{task['id']}?workspace_id={WS}", json={"title": "Still mine"}
    )
    assert patched.json()["workspace_id"] == WS
