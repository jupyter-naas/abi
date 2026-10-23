from __future__ import annotations

from types import SimpleNamespace

import pytest
from fastapi import FastAPI, HTTPException
from fastapi.testclient import TestClient
from naas_abi.apps.nexus.apps.api.app.core.config import FeatureFlagsConfig
from naas_abi.apps.nexus.apps.api.app.core.feature_flags import build_feature_flags
from naas_abi.apps.nexus.apps.api.app.services.board.adapters.primary import (
    board__primary_adapter__FastAPI as api,
)
from naas_abi.apps.nexus.apps.api.app.services.board.adapters.secondary.memory import (
    InMemoryBoardMemberDirectory,
    InMemoryBoardStore,
)
from naas_abi.apps.nexus.apps.api.app.services.board.service import BoardService

WS = "ws-1"
OTHER_WS = "ws-2"
USER = "u-1"


@pytest.fixture
def client_for(monkeypatch):
    service = BoardService(
        InMemoryBoardStore(), InMemoryBoardMemberDirectory({WS: {USER, "u-2"}, OTHER_WS: {USER}})
    )

    def make(role: str | None, *, overrides: dict[str, bool] | None = None) -> TestClient:
        async def access(user_id, workspace_id):
            if role is None:
                raise HTTPException(status_code=403, detail="no access")
            return role

        async def flags(workspace_id, caller_role):
            # The deployment defaults, as resolved for the workspace listing.
            return build_feature_flags(
                role=caller_role,
                feature_flags_config=FeatureFlagsConfig(),
                workspace_slug=None,
                workspace_id=workspace_id,
                workspace_override=overrides,
            )

        monkeypatch.setattr(api, "require_workspace_access", access)
        monkeypatch.setattr(api, "_caller_flags", flags)
        app = FastAPI()
        app.include_router(api.router, prefix="/api/board")
        app.dependency_overrides[api.get_current_user_required] = lambda: SimpleNamespace(id=USER)
        app.dependency_overrides[api.get_board_service] = lambda: service
        return TestClient(app)

    return make


@pytest.mark.parametrize("role", ["owner", "admin"])
def test_owners_and_admins_use_the_board(client_for, role):
    client = client_for(role)

    res = client.post(f"/api/board/iterations?workspace_id={WS}", json={"date": "2026-10-22"})

    assert res.status_code == 200
    assert res.json()["start_date"] == "2026-10-19"
    assert res.json()["end_date"] == "2026-10-25"
    assert res.json()["iso_week"] == "2026-W43"


@pytest.mark.parametrize("role", ["member", "viewer"])
def test_members_and_viewers_are_refused_by_default(client_for, role):
    client = client_for(role)

    assert client.get(f"/api/board/iterations?workspace_id={WS}").status_code == 403
    assert (
        client.post(f"/api/board/tasks?workspace_id={WS}", json={"title": "T"}).status_code == 403
    )


def test_workspace_override_opens_the_board_to_members(client_for):
    client = client_for("member", overrides={"board": True})

    assert client.get(f"/api/board/iterations?workspace_id={WS}").status_code == 200


def test_outsiders_are_refused(client_for):
    client = client_for(None)

    assert client.get(f"/api/board/iterations?workspace_id={WS}").status_code == 403


def test_task_lifecycle_over_http(client_for):
    client = client_for("admin")
    iteration = client.post(
        f"/api/board/iterations?workspace_id={WS}", json={"date": "2026-10-22"}
    ).json()

    created = client.post(
        f"/api/board/tasks?workspace_id={WS}",
        json={"title": "Write spec", "iteration_id": iteration["id"], "labels": ["Feature"]},
    )
    assert created.status_code == 201
    task = created.json()
    assert task["stage"] == "inbox"
    assert task["created_by"] == USER

    patched = client.patch(
        f"/api/board/tasks/{task['id']}?workspace_id={WS}",
        json={"stage": "review", "assignee_ids": ["u-2"], "due_date": "2026-11-02"},
    )
    assert patched.status_code == 200
    assert patched.json()["stage"] == "review"
    assert patched.json()["assignee_ids"] == ["u-2"]
    assert patched.json()["due_date"] == "2026-11-02"
    # Fields not sent stay as they were.
    assert patched.json()["labels"] == ["Feature"]

    cleared = client.patch(
        f"/api/board/tasks/{task['id']}?workspace_id={WS}", json={"due_date": None}
    )
    assert cleared.json()["due_date"] is None

    listed = client.get(f"/api/board/tasks?workspace_id={WS}&iteration_id={iteration['id']}").json()
    assert [t["id"] for t in listed] == [task["id"]]

    assert (
        client.post(
            f"/api/board/tasks/{task['id']}/comments?workspace_id={WS}", json={"body": "LGTM"}
        ).status_code
        == 201
    )
    comments = client.get(f"/api/board/tasks/{task['id']}/comments?workspace_id={WS}").json()
    assert [c["body"] for c in comments] == ["LGTM"]

    activity = client.get(f"/api/board/tasks/{task['id']}/activity?workspace_id={WS}").json()
    assert [a["field"] for a in activity] == ["created", "stage", "assignees"]

    archived = client.post(f"/api/board/tasks/{task['id']}/archive?workspace_id={WS}").json()
    assert archived["archived"] is True
    assert (
        client.get(f"/api/board/tasks?workspace_id={WS}&iteration_id={iteration['id']}").json()
        == []
    )
    restored = client.post(f"/api/board/tasks/{task['id']}/restore?workspace_id={WS}").json()
    assert restored["archived"] is False

    assert client.delete(f"/api/board/tasks/{task['id']}?workspace_id={WS}").status_code == 204
    assert client.delete(f"/api/board/tasks/{task['id']}?workspace_id={WS}").status_code == 404


def test_backlog_goal_and_carry_over_over_http(client_for):
    client = client_for("owner")
    iteration = client.post(
        f"/api/board/iterations?workspace_id={WS}", json={"date": "2026-10-22"}
    ).json()
    backlog = client.post(f"/api/board/tasks?workspace_id={WS}", json={"title": "Idea"}).json()
    open_task = client.post(
        f"/api/board/tasks?workspace_id={WS}",
        json={"title": "Open", "iteration_id": iteration["id"], "stage": "in_progress"},
    ).json()

    assert [
        t["id"] for t in client.get(f"/api/board/tasks?workspace_id={WS}&backlog=true").json()
    ] == [backlog["id"]]
    assert client.get(f"/api/board/tasks?workspace_id={WS}").status_code == 422

    goal = client.patch(
        f"/api/board/iterations/{iteration['id']}?workspace_id={WS}", json={"goal": "Ship it"}
    )
    assert goal.json()["goal"] == "Ship it"

    carried = client.post(f"/api/board/iterations/{iteration['id']}/carry-over?workspace_id={WS}")
    assert carried.status_code == 200
    body = carried.json()
    assert body["iteration"]["start_date"] == "2026-10-26"
    assert [t["id"] for t in body["moved"]] == [open_task["id"]]


def test_validation_and_workspace_isolation_over_http(client_for):
    client = client_for("admin")
    task = client.post(f"/api/board/tasks?workspace_id={WS}", json={"title": "T"}).json()

    assert (
        client.post(
            f"/api/board/tasks?workspace_id={WS}", json={"title": "T", "stage": "doing"}
        ).status_code
        == 422
    )
    assert (
        client.post(
            f"/api/board/tasks?workspace_id={WS}", json={"title": "T", "assignee_ids": ["u-x"]}
        ).status_code
        == 422
    )
    assert (
        client.patch(
            f"/api/board/tasks/{task['id']}?workspace_id={OTHER_WS}", json={"title": "x"}
        ).status_code
        == 404
    )
    assert client.get(f"/api/board/tasks?workspace_id={OTHER_WS}&backlog=true").json() == []
