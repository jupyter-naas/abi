"""Presence and broadcast are IAM's: a viewer sees who is present and sends nothing."""

from __future__ import annotations

from types import SimpleNamespace

import pytest
from fastapi import FastAPI, Request
from fastapi.testclient import TestClient
from naas_abi.apps.nexus.apps.api.app.api.endpoints.auth import (
    User,
    get_current_user_required,
)
from naas_abi.apps.nexus.apps.api.app.core.config import FeatureFlagsConfig
from naas_abi.apps.nexus.apps.api.app.services.iam.testing import NexusIam
from naas_abi.apps.nexus.apps.api.app.services.websocket.adapters.primary import (
    websocket__primary_adapter__FastAPI as websocket_api,
)


@pytest.fixture
def world(team: NexusIam, monkeypatch: pytest.MonkeyPatch):
    broadcasts: list[tuple[str, str, dict]] = []

    async def broadcast(workspace_id, event, data):
        broadcasts.append((workspace_id, event, data))
        return {"status": "broadcasted", "workspace_id": workspace_id}

    monkeypatch.setattr(websocket_api.service, "broadcast_to_workspace", broadcast)
    monkeypatch.setattr(
        websocket_api.service, "get_workspace_presence", lambda _workspace_id: ["u1"]
    )
    monkeypatch.setattr(
        websocket_api.service, "get_user_workspaces", lambda _user_id: ["ws-1", "ws-2"]
    )
    app = FastAPI()
    app.include_router(websocket_api.router)

    def current_user(request: Request) -> User:
        return User.model_construct(id=request.headers["x-user"], email="u@example.com")

    app.dependency_overrides[get_current_user_required] = current_user
    return SimpleNamespace(iam=team, broadcasts=broadcasts, client=TestClient(app))


def call(world, user: str, method: str, path: str, **kwargs):
    return world.client.request(method, path, headers={"x-user": user}, **kwargs)


BODY = {"workspace_id": "ws-1", "event": "workspace.alert", "data": {"ok": True}}


@pytest.mark.parametrize("user", ["member", "admin", "owner"])
def test_members_and_up_broadcast(world, user: str) -> None:
    response = call(world, user, "POST", "/websocket/broadcast", json=BODY)

    assert response.status_code == 200
    assert response.json() == {"status": "broadcasted", "workspace_id": "ws-1"}
    assert world.broadcasts == [("ws-1", "workspace.alert", {"ok": True})]


@pytest.mark.parametrize("user", ["viewer", "stranger"])
def test_a_viewer_and_a_stranger_cannot_broadcast(world, user: str) -> None:
    response = call(world, user, "POST", "/websocket/broadcast", json=BODY)

    assert response.status_code == 403
    assert world.broadcasts == []


def test_a_member_cannot_broadcast_into_another_workspace(world) -> None:
    world.iam.workspace("org-1", "ws-2")

    response = call(
        world, "member", "POST", "/websocket/broadcast", json={**BODY, "workspace_id": "ws-2"}
    )

    assert response.status_code == 403
    assert world.broadcasts == []


@pytest.mark.parametrize("user", ["viewer", "member", "admin", "owner"])
def test_every_role_sees_the_presence_of_its_workspace(world, user: str) -> None:
    response = call(world, user, "GET", "/websocket/presence/ws-1")

    assert response.status_code == 200
    assert response.json() == {"workspace_id": "ws-1", "users": ["u1"], "count": 1}


def test_a_stranger_does_not_see_presence(world) -> None:
    assert call(world, "stranger", "GET", "/websocket/presence/ws-1").status_code == 403


def test_presence_does_not_depend_on_the_maps_section(team: NexusIam, world) -> None:
    """Presence is the workspace's, shown in every section: the flags of a section
    (maps here) do not close it."""
    flags = FeatureFlagsConfig(
        enabled_features=["chat"], role_baseline={"owner": ["chat"], "viewer": ["chat"]}
    )
    nexus = NexusIam(flags)
    nexus.grant("viewer", "viewer", nexus.workspace("org-1", "ws-1"))

    with nexus.installed():
        response = call(world, "viewer", "GET", "/websocket/presence/ws-1")

    assert response.status_code == 200


def test_user_presence_rejects_other_user(world) -> None:
    response = call(world, "viewer", "GET", "/websocket/presence/user/member")

    assert response.status_code == 403


def test_user_presence_allows_current_user(world) -> None:
    response = call(world, "viewer", "GET", "/websocket/presence/user/viewer")

    assert response.json() == {"user_id": "viewer", "workspaces": ["ws-1", "ws-2"], "count": 2}
