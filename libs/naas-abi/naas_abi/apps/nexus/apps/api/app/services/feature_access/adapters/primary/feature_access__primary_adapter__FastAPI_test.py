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
    ALPHA,
    FEATURES,
    acme,
    audit,
    enabled_features,
    nexus,
    ontologies,
    service,
)
from naas_abi.apps.nexus.apps.api.app.services.iam.memberships import MEMBERSHIPS

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
    assert body["members_group"]["name"] == "Alpha workspace"
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


def test_the_offer_reads_as_configuration_and_saves_as_the_caller(client):
    path = "/api/workspaces/alpha/offer"
    assert client.get(path, headers={"x-user": "dave"}).status_code == 403
    assert client.get(path, headers={"x-user": "olivia"}).json()["offered"]["agents"] == []
    change = {"kind": "agents", "module": "acme.sales", "name": "*", "offered": True}
    saved = client.put(path, json={"changes": [change]}, headers={"x-user": "olivia"})
    assert saved.status_code == 200
    assert saved.json()["offered"]["agents"] == [{"module": "acme.sales", "name": "*"}]
    beyond = {**change, "module": "other.module", "name": "X"}
    assert (
        client.put(path, json={"changes": [beyond]}, headers={"x-user": "olivia"}).status_code
        == 422
    )
    assert client.put(path, json={"changes": []}, headers={"x-user": "olivia"}).status_code == 422


def test_the_files_given_are_read_with_the_offer_and_saved_as_the_caller(client):
    """Olivia, Acme's owner, gives Acme's Organization Files; Platform Files is the
    platform admin's (403); a mode a section does not have or no change at all is 422."""
    path = "/api/workspaces/alpha/offer/files"
    state = client.get("/api/workspaces/alpha/offer", headers={"x-user": "olivia"}).json()
    rows = {row["key"]: row for row in state["files"]}
    assert set(rows) == {"org_files", "platform_files", "system_files"}
    assert rows["org_files"]["mode"] == "off" and rows["org_files"]["editable"]
    assert not rows["platform_files"]["editable"]
    assert state["my_files"] == {"members": "write", "viewers": "read"}
    saved = client.put(path, json={"org_files": "read"}, headers={"x-user": "olivia"})
    assert saved.status_code == 200
    assert {r["key"]: r["mode"] for r in saved.json()["files"]}["org_files"] == "read"
    refused = client.put(path, json={"platform_files": "read"}, headers={"x-user": "olivia"})
    assert refused.status_code == 403
    assert (
        client.put(path, json={"system_files": "write"}, headers={"x-user": "root"}).status_code
        == 422
    )
    assert client.put(path, json={}, headers={"x-user": "olivia"}).status_code == 422
    assert client.put(path, json={"org_files": "read"}, headers={"x-user": "dave"}).status_code in (
        403,
        404,
    )


class TestOntologies:
    """On a deployment with the ontology feature."""

    @pytest.fixture
    def enabled_features(self) -> list[str]:
        return [*FEATURES, "ontology"]

    @pytest.fixture
    def client(self, ontologies):  # noqa: F811
        previous = runtime.configure(lambda: ontologies)
        app = FastAPI()
        app.include_router(router, prefix="/api/workspaces")
        app.dependency_overrides[get_current_user_required] = _by_header
        yield TestClient(app)
        runtime.configure(previous)

    @pytest.mark.asyncio
    async def test_the_ontologies_are_read_with_the_offer_and_saved_as_the_caller(self, client):
        """Olivia, Acme's owner, assigns any ontology; Alpha's admin Frank, who may
        not, is refused one (403) and removes one; a file outside the catalog or no
        change is 422; a member changes nothing."""
        path = "/api/workspaces/alpha/offer/ontologies"
        olivia, frank = {"x-user": "olivia"}, {"x-user": "frank"}
        state = client.get("/api/workspaces/alpha/offer", headers=olivia).json()
        assert state["ontologies"]["offered"] == ["Core:BFO.ttl"]
        rows = {row["id"]: row for row in state["ontologies"]["rows"]}
        assert rows["core:bfo.ttl"]["offered"] and rows["core:agent.ttl"]["editable"]
        saved = client.put(path, json={"changes": {"core:agent.ttl": True}}, headers=olivia)
        assert saved.status_code == 200, saved.text
        assert saved.json()["ontologies"]["offered"] == ["Core:BFO.ttl", "core:agent.ttl"]
        await MEMBERSHIPS.grant("frank", "admin", ALPHA)
        refused = client.put(path, json={"changes": {"acme.sales:sales.ttl": True}}, headers=frank)
        assert refused.status_code == 403
        assert "AssignOntology" in refused.json()["detail"]
        removed = client.put(path, json={"changes": {"core:agent.ttl": False}}, headers=frank)
        assert removed.status_code == 200, removed.text
        assert removed.json()["ontologies"]["offered"] == ["Core:BFO.ttl"]
        unknown = client.put(path, json={"changes": {"nope:Nope.ttl": True}}, headers=olivia)
        assert unknown.status_code == 422
        assert client.put(path, json={"changes": {}}, headers=olivia).status_code == 422
        member = client.put(
            path, json={"changes": {"core:bfo.ttl": False}}, headers={"x-user": "dave"}
        )
        assert member.status_code in (403, 404)
