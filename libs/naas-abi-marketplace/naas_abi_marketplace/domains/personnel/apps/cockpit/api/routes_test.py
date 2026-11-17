"""The Personnel Cockpit's datasets answer only a member of the workspace the
cockpit is opened in (or, without Nexus, the engine's API key), and its errors
name no path on the server."""

from __future__ import annotations

import importlib
from types import SimpleNamespace

import naas_abi_marketplace.domains.personnel.apps.cockpit.data_store as ds
import pytest
from fastapi import FastAPI, Header, HTTPException
from fastapi.testclient import TestClient
from naas_abi_core.services.object_storage.ObjectStorageFactory import (
    ObjectStorageFactory,
)
from naas_abi_core.utils.StorageUtils import StorageUtils
from naas_abi_marketplace.domains.personnel.apps.cockpit.api import access
from naas_abi_marketplace.domains.personnel.apps.cockpit.config_loader import (
    public_page_ids,
)

KEY = "deployment-key"
MEMBERS = {("usr-ada", "ws-1")}


@pytest.fixture
def page(tmp_path, monkeypatch: pytest.MonkeyPatch) -> str:
    store = ObjectStorageFactory.ObjectStorageServiceFS(str(tmp_path))
    monkeypatch.setattr(ds, "_datastore_root", lambda: str(tmp_path))
    monkeypatch.setattr(ds, "get_object_storage", lambda: store)
    monkeypatch.setattr(ds, "get_storage_utils", lambda: StorageUtils(store))
    page = min(public_page_ids())
    ds.publish_json(f"entities/acme/{page}/team.json", {"rows": [{"name": "Ada"}]})
    monkeypatch.setenv("ABI_API_KEY", KEY)
    return page


def client(monkeypatch: pytest.MonkeyPatch, nexus) -> TestClient:
    monkeypatch.setattr(access, "_nexus", lambda: nexus)
    from naas_abi_marketplace.domains.personnel.apps.cockpit.api import routes

    app = FastAPI()
    app.include_router(importlib.reload(routes).router, prefix="/api/personnel-cockpit")
    return TestClient(app)


def nexus():
    def current_user(authorization: str = Header("")) -> SimpleNamespace:
        user = authorization.removeprefix("Bearer ").strip()
        if not user:
            raise HTTPException(status_code=401, detail="Not authenticated")
        return SimpleNamespace(id=user)

    async def require_workspace_access(user_id: str, workspace_id: str) -> str:
        if (user_id, workspace_id) not in MEMBERS:
            raise HTTPException(status_code=403, detail="No access")
        return "member"

    return current_user, require_workspace_access


def test_cockpit_keeps_to_workspace_members(page: str, monkeypatch) -> None:
    c = client(monkeypatch, nexus())
    url = f"/api/personnel-cockpit/entities/acme/{page}/team.json"
    ada = {"Authorization": "Bearer usr-ada"}

    assert c.get(url).status_code == 401
    assert c.get(url, headers=ada).status_code == 403  # no workspace named
    assert c.get(url, params={"workspace_id": "ws-2"}, headers=ada).status_code == 403
    assert (
        c.get(
            url,
            params={"workspace_id": "ws-1"},
            headers={"Authorization": "Bearer usr-bob"},
        ).status_code
        == 403
    )
    member = c.get(url, params={"workspace_id": "ws-1"}, headers=ada)
    assert member.status_code == 200 and member.json()["rows"][0]["name"] == "Ada"
    assert c.get("/api/personnel-cockpit/config").status_code == 401


def test_cockpit_without_nexus_keeps_to_the_api_key(page: str, monkeypatch) -> None:
    c = client(monkeypatch, None)
    url = f"/api/personnel-cockpit/entities/acme/{page}/team.json"

    assert c.get(url).status_code == 401
    assert c.get(url, headers={"Authorization": "Bearer other"}).status_code == 401
    assert c.get(url, headers={"Authorization": f"Bearer {KEY}"}).status_code == 200


def test_cockpit_errors_keep_server_paths_out(page: str, tmp_path, monkeypatch) -> None:
    c = client(monkeypatch, None)

    missing = c.get(
        f"/api/personnel-cockpit/entities/nope/{page}/x.json",
        headers={"Authorization": f"Bearer {KEY}"},
    )

    assert missing.status_code == 404
    assert str(tmp_path) not in missing.text
    assert "expected_local_path" not in missing.text
