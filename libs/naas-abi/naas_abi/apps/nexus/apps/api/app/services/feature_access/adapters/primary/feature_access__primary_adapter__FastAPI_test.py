"""The feature access routes: read as the workspace's configuration (its admins),
saved as IAM's writes made as the caller, a malformed batch refused whole."""

from __future__ import annotations

from types import SimpleNamespace

import pytest
from fastapi import FastAPI, HTTPException, Request
from fastapi.testclient import TestClient
from naas_abi.apps.nexus.apps.api.app.services.auth.adapters.primary.auth__primary_adapter__dependencies import (  # noqa: E501
    get_current_user_required,
)
from naas_abi.apps.nexus.apps.api.app.services.feature_access import runtime
from naas_abi.apps.nexus.apps.api.app.services.feature_access.adapters.primary.feature_access__primary_adapter__FastAPI import (  # noqa: E501
    router,
)
from naas_abi.apps.nexus.apps.api.app.services.feature_access.service_test import (  # noqa: F401
    acme,
    audit,
    nexus,
    service,
)

PATH = "/api/workspaces/alpha/feature-access"


def _by_header(request: Request) -> SimpleNamespace:
    user = request.headers.get("x-user")
    if not user:
        raise HTTPException(401, "Not authenticated")
    return SimpleNamespace(id=user, email=f"{user}@example.com", name=user)


@pytest.fixture
def client(acme, service):  # noqa: F811
    previous = runtime.configure(lambda: service)
    app = FastAPI()
    app.include_router(router, prefix="/api/workspaces")
    app.dependency_overrides[get_current_user_required] = _by_header
    yield TestClient(app)
    runtime.configure(previous)


def test_its_admins_read_it_and_a_member_does_not(client):
    found = client.get(PATH, headers={"x-user": "olivia"})
    assert found.status_code == 200
    body = found.json()
    assert [row["key"] for row in body["features"]] == ["chat", "files", "marketplace"]
    assert body["access_policy"]["name"] == "Alpha access"
    assert body["members_group"]["name"] == "Alpha members"
    assert client.get(PATH, headers={"x-user": "dave"}).status_code == 403


def test_a_batch_saves_as_the_caller_and_a_malformed_one_changes_nothing(client):
    for bad in (
        {"changes": []},
        {"changes": [{"feature": "chat", "choice": "sometimes"}]},
        {"changes": [{"feature": "chat", "choice": "everyone", "principals": ["usr_x"]}]},
        {"changes": [{"feature": "nope", "choice": "everyone"}]},
    ):
        assert client.put(PATH, json=bad, headers={"x-user": "olivia"}).status_code == 422
    saved = client.put(
        PATH,
        json={
            "changes": [
                {"feature": "chat", "choice": "everyone"},
                {"feature": "files", "choice": "nobody"},
            ]
        },
        headers={"x-user": "olivia"},
    )
    assert saved.status_code == 200
    rows = {row["key"]: row for row in saved.json()["features"]}
    assert saved.json()["errors"] == {}
    assert (rows["chat"]["choice"], rows["files"]["choice"]) == ("everyone", "nobody")
    refused = client.put(
        PATH,
        json={"changes": [{"feature": "chat", "choice": "nobody"}]},
        headers={"x-user": "dave"},
    )
    assert refused.status_code == 200 and "chat" in refused.json()["errors"]
