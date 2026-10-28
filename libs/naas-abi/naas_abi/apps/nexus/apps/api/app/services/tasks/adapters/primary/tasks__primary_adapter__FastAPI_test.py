"""``/api/tasks`` decided by IAM: the ``tasks`` feature, then each route's action.

A real IAM (``team``: ``owner``, ``admin``, ``member``, ``viewer`` of ``ws-1`` in
``org-1``, and ``stranger``), the deployment's feature defaults (owners and
admins have ``tasks``), and the routes as mounted. Requests act as the user the
``X-User`` header names; ``X-Key-Scope: read`` narrows the call as a read-only
personal key does.
"""

from __future__ import annotations

import asyncio
from dataclasses import replace

import pytest
from fastapi import FastAPI, Request
from fastapi.testclient import TestClient
from naas_abi.apps.nexus.apps.api.app.services.auth.adapters.primary.auth__primary_adapter__dependencies import (  # noqa: E501
    get_current_user_required,
)
from naas_abi.apps.nexus.apps.api.app.services.iam.names import workspace_scope
from naas_abi.apps.nexus.apps.api.app.services.iam.testing import NexusIam
from naas_abi.apps.nexus.apps.api.app.services.tasks.adapters.primary import (
    tasks__primary_adapter__FastAPI as api,
)
from naas_abi.apps.nexus.apps.api.app.services.tasks.adapters.secondary.memory import (
    InMemoryTasksMemberDirectory,
    InMemoryTasksStore,
)
from naas_abi.apps.nexus.apps.api.app.services.tasks.service import TasksService
from naas_abi_core.engine.call_context import use_call_context
from starlette.types import ASGIApp, Receive, Scope, Send

WS = "ws-1"
OTHER_WS = "ws-2"
ROLES = ("owner", "admin", "member", "viewer")
# What a personal key limited to reading carries (its ``abi_scope``).
READ_ONLY_KEY = (
    {
        "effect": "Allow",
        "actions": ["nexus:UseFeature", "nexus:List*", "nexus:Get*"],
        "resources": ["*"],
    },
)
TASKS_FEATURE = ["nexus:UseFeature"], ["${scope}:nexus:feature/tasks"]


class AsCaller:
    """Run each request as ``X-User``: ``api`` on behalf of them, narrowed by
    ``X-Key-Scope: read`` as a read-only key's call is."""

    def __init__(self, app: ASGIApp) -> None:
        self.app = app

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        headers = dict(scope.get("headers") or [])
        ctx = NexusIam.context(headers.get(b"x-user", b"").decode() or None)
        if headers.get(b"x-key-scope") == b"read":
            ctx = replace(ctx, scope=READ_ONLY_KEY)
        with use_call_context(ctx):
            await self.app(scope, receive, send)


@pytest.fixture
def client_for(team):
    """``client_for(user)``: a client acting as ``user`` (``key="read"`` for a
    read-only key). ``client_for.service`` adds records as anyone."""
    service = TasksService(
        InMemoryTasksStore(),
        InMemoryTasksMemberDirectory({WS: {*ROLES}, OTHER_WS: {"owner", "admin"}}),
    )
    team.workspace("org-1", OTHER_WS)
    app = FastAPI()
    app.include_router(api.router, prefix="/api/tasks")
    app.dependency_overrides[api.get_tasks_service] = lambda: service

    def current_user(request: Request):
        from types import SimpleNamespace

        return SimpleNamespace(id=request.headers["x-user"], is_superadmin=False)

    app.dependency_overrides[get_current_user_required] = current_user
    app.add_middleware(AsCaller)

    def make(user: str, *, key: str | None = None) -> TestClient:
        headers = {"x-user": user}
        if key:
            headers["x-key-scope"] = key
        return TestClient(app, headers=headers)

    make.service = service  # type: ignore[attr-defined]
    make.iam = team  # type: ignore[attr-defined]
    return make


def _settings_payload(settings: dict) -> dict:
    keys = (
        "iteration_weeks",
        "iteration_start_day",
        "stages",
        "priorities",
        "default_stage",
        "suggested_labels",
    )
    return {**{k: settings[k] for k in keys}, "today": "2026-10-22"}


def _grant_tasks(team: NexusIam, user: str) -> None:
    """A feature policy giving ``user`` the ``tasks`` feature in ``ws-1``."""
    team.allow(user, *TASKS_FEATURE, workspace_scope("org-1", WS))


@pytest.mark.parametrize("user", ["owner", "admin"])
def test_owners_and_admins_use_tasks_and_change_the_settings(client_for, user):
    client = client_for(user)

    iteration = client.post(f"/api/tasks/iterations?workspace_id={WS}", json={"date": "2026-10-22"})
    assert iteration.status_code == 200, iteration.text
    assert iteration.json()["iso_week"] == "2026-W43"
    task = client.post(f"/api/tasks?workspace_id={WS}", json={"title": "T"})
    assert task.status_code == 201, task.text
    comment = client.post(
        f"/api/tasks/{task.json()['id']}/comments?workspace_id={WS}", json={"body": "Hi"}
    )
    assert comment.status_code == 201

    settings = client.get(f"/api/tasks/settings?workspace_id={WS}").json()
    assert (settings["can_edit"], settings["can_moderate"]) == (True, True)
    saved = client.put(
        f"/api/tasks/settings?workspace_id={WS}",
        json={**_settings_payload(settings), "iteration_weeks": 2},
    )
    assert saved.status_code == 200, saved.text
    assert saved.json()["iteration_weeks"] == 2


@pytest.mark.parametrize("user", ["member", "viewer"])
def test_members_and_viewers_are_refused_by_default(client_for, user):
    client = client_for(user)

    for res in (
        client.get(f"/api/tasks/iterations?workspace_id={WS}"),
        client.get(f"/api/tasks/settings?workspace_id={WS}"),
        client.post(f"/api/tasks?workspace_id={WS}", json={"title": "T"}),
    ):
        assert res.status_code == 403
        assert res.json()["detail"] == "This feature is not available to you in this workspace"


def test_a_member_given_the_feature_by_a_policy_uses_tasks_but_not_the_settings(client_for):
    _grant_tasks(client_for.iam, "member")
    member = client_for("member")

    task = member.post(f"/api/tasks?workspace_id={WS}", json={"title": "T"})
    assert task.status_code == 201, task.text
    assert member.get(f"/api/tasks?workspace_id={WS}").status_code == 200
    settings = member.get(f"/api/tasks/settings?workspace_id={WS}").json()
    assert (settings["can_edit"], settings["can_moderate"]) == (False, False)
    assert (
        member.put(
            f"/api/tasks/settings?workspace_id={WS}", json=_settings_payload(settings)
        ).status_code
        == 403
    )


def test_a_member_given_the_feature_by_the_org_overlay_uses_tasks():
    nexus = NexusIam(org_overlays={"org-1": {"member": ["chat", "tasks"]}})
    scope = nexus.workspace("org-1", WS)
    nexus.grant("member", "member", scope)
    service = TasksService(InMemoryTasksStore(), InMemoryTasksMemberDirectory({WS: {"member"}}))
    app = FastAPI()
    app.include_router(api.router, prefix="/api/tasks")
    app.dependency_overrides[api.get_tasks_service] = lambda: service
    app.dependency_overrides[get_current_user_required] = lambda: type("U", (), {"id": "member"})
    app.add_middleware(AsCaller)
    with nexus.installed():
        member = TestClient(app, headers={"x-user": "member"})
        assert member.post(f"/api/tasks?workspace_id={WS}", json={"title": "T"}).status_code == 201
        assert member.put(f"/api/tasks/settings?workspace_id={WS}", json={}).status_code == 403


def test_a_viewer_given_the_feature_reads_and_writes_nothing(client_for):
    _grant_tasks(client_for.iam, "viewer")
    task = client_for("owner").post(f"/api/tasks?workspace_id={WS}", json={"title": "T"}).json()
    viewer = client_for("viewer")

    for url in (
        f"/api/tasks?workspace_id={WS}",
        f"/api/tasks/iterations?workspace_id={WS}",
        f"/api/tasks/settings?workspace_id={WS}",
        f"/api/tasks/feed?workspace_id={WS}",
        f"/api/tasks/{task['id']}/comments?workspace_id={WS}",
        f"/api/tasks/{task['id']}/activity?workspace_id={WS}",
    ):
        assert viewer.get(url).status_code == 200, url
    for res in (
        viewer.post(f"/api/tasks?workspace_id={WS}", json={"title": "T"}),
        viewer.post(f"/api/tasks/iterations?workspace_id={WS}", json={"date": "2026-10-22"}),
        viewer.patch(f"/api/tasks/{task['id']}?workspace_id={WS}", json={"title": "x"}),
        viewer.post(f"/api/tasks/{task['id']}/comments?workspace_id={WS}", json={"body": "x"}),
        viewer.delete(f"/api/tasks/{task['id']}?workspace_id={WS}"),
    ):
        assert res.status_code == 403


def test_a_stranger_is_refused(client_for):
    stranger = client_for("stranger")

    res = stranger.get(f"/api/tasks/iterations?workspace_id={WS}")
    assert res.status_code == 403
    assert res.json()["detail"] == "You do not have access to this workspace"
    assert stranger.post(f"/api/tasks?workspace_id={WS}", json={"title": "T"}).status_code == 403


def test_a_workspace_without_tasks_in_its_set_refuses_all_but_the_platform_admin(client_for):
    client_for.iam.put_set("org-1", WS, features=["chat", "settings"])
    client_for.iam.platform_admin("root")

    for user in ROLES:
        assert client_for(user).get(f"/api/tasks?workspace_id={WS}").status_code == 403, user
    root = client_for("root")
    assert root.get(f"/api/tasks?workspace_id={WS}").status_code == 200
    assert root.post(f"/api/tasks?workspace_id={WS}", json={"title": "T"}).status_code == 201


def test_a_read_only_key_reads_and_cannot_write(client_for):
    key = client_for("owner", key="read")

    assert key.get(f"/api/tasks?workspace_id={WS}").status_code == 200
    assert key.get(f"/api/tasks/settings?workspace_id={WS}").json()["can_edit"] is False
    assert key.post(f"/api/tasks?workspace_id={WS}", json={"title": "T"}).status_code == 403
    assert (
        key.post(
            f"/api/tasks/iterations?workspace_id={WS}", json={"date": "2026-10-22"}
        ).status_code
        == 403
    )
    # The same owner signed in writes: the narrowing was the key's.
    assert (
        client_for("owner").post(f"/api/tasks?workspace_id={WS}", json={"title": "T"}).status_code
        == 201
    )


def test_authors_remove_their_comments_and_admins_anyones(client_for):
    _grant_tasks(client_for.iam, "member")
    owner, member = client_for("owner"), client_for("member")
    task = owner.post(f"/api/tasks?workspace_id={WS}", json={"title": "T"}).json()
    comments = f"/api/tasks/{task['id']}/comments"
    theirs = owner.post(f"{comments}?workspace_id={WS}", json={"body": "Owner's"}).json()
    mine = member.post(f"{comments}?workspace_id={WS}", json={"body": "Member's"}).json()

    assert member.delete(f"{comments}/{theirs['id']}?workspace_id={WS}").status_code == 403
    assert member.delete(f"{comments}/{mine['id']}?workspace_id={WS}").status_code == 204
    again = member.post(f"{comments}?workspace_id={WS}", json={"body": "Again"}).json()
    assert (
        client_for("admin").delete(f"{comments}/{again['id']}?workspace_id={WS}").status_code == 204
    )
    assert [c["id"] for c in owner.get(f"{comments}?workspace_id={WS}").json()] == [theirs["id"]]


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
    assert task["created_by"] == "admin"

    patched = client.patch(
        f"/api/tasks/{task['id']}?workspace_id={WS}",
        json={"stage": "review", "assignee_ids": ["member"], "due_date": "2026-11-02"},
    )
    assert patched.status_code == 200
    assert patched.json()["stage"] == "review"
    assert patched.json()["assignee_ids"] == ["member"]
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

    # Someone else's comment: the owner moderates it.
    other = asyncio.run(client_for.service.add_comment(WS, task["id"], "Theirs", user_id="member"))
    one = f"/api/tasks/{task['id']}/comments/{other.id}?workspace_id={WS}"
    assert owner.delete(one).status_code == 204
    # Removing a comment removes its replies.
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

    # A member given the feature reads the settings and cannot change them.
    _grant_tasks(client_for.iam, "member")
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
