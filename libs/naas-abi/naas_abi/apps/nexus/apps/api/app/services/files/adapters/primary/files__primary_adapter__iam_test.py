"""The files router decides with IAM: viewers read, members write, admins reach the
system drive, and nobody leaves their workspace's drive.

The real router over a real IAM (``team``: ``ws-1`` of ``org-1`` with an owner, an
admin, a member and a viewer, plus a stranger) and a filesystem object storage.
"""

from __future__ import annotations

from types import SimpleNamespace

import pytest
from fastapi import FastAPI
from httpx import ASGITransport, AsyncClient
from naas_abi.apps.nexus.apps.api.app.core.config import FeatureFlagsConfig
from naas_abi.apps.nexus.apps.api.app.core.feature_flags import KNOWN_FEATURE_KEYS
from naas_abi.apps.nexus.apps.api.app.services.exceptions import (
    register_service_exception_handlers,
)
from naas_abi.apps.nexus.apps.api.app.services.files import placement
from naas_abi.apps.nexus.apps.api.app.services.files.adapters.primary import (
    files__primary_adapter__FastAPI as files_api,
)
from naas_abi.apps.nexus.apps.api.app.services.files.adapters.primary.files__primary_adapter__dependencies import (  # noqa: E501
    get_files_service,
)
from naas_abi.apps.nexus.apps.api.app.services.files.service import FilesService
from naas_abi.apps.nexus.apps.api.app.services.files.testing import (
    with_personal_drive_rows,
)
from naas_abi.apps.nexus.apps.api.app.services.iam.testing import NexusIam
from naas_abi_core.services.iam import roles
from naas_abi_core.services.object_storage.adapters.secondary.ObjectStorageSecondaryAdapterFS import (  # noqa: E501
    ObjectStorageSecondaryAdapterFS,
)
from naas_abi_core.services.object_storage.ObjectStorageService import ObjectStorageService

WS1 = "naas_abi/workspace-drive/ws-1"
WS2 = "naas_abi/workspace-drive/ws-2"


@pytest.fixture(autouse=True)
def _personal_drive_rows(monkeypatch) -> None:
    monkeypatch.setattr(roles, "PLATFORM_TYPES", with_personal_drive_rows())
    placement._PLACED.clear()  # each test has its own IAM: nothing is placed in it yet


@pytest.fixture
def storage(tmp_path) -> ObjectStorageService:
    storage = ObjectStorageService(ObjectStorageSecondaryAdapterFS(str(tmp_path)))
    storage.put_object(WS1, "readme.md", b"# one")
    storage.put_object(f"{WS1}/docs", "a.txt", b"a")
    storage.put_object(WS2, "secret.md", b"# two")
    storage.put_object("naas_abi/platform-drive", "shared.md", b"# shared")
    storage.put_object("naas_abi/my-drive/viewer", "mine.md", b"# viewer's")
    storage.put_object("naas_abi/my-drive/member", "mine.md", b"# member's")
    return storage


@pytest.fixture
def drives(monkeypatch) -> dict[str, bool]:
    """The workspace settings ``platform_drive_enabled`` and ``system_drive_enabled``."""
    settings = {"platform_drive_enabled": True, "system_drive_enabled": True}

    async def setting(workspace_id: str, name: str) -> bool:
        return settings[name]

    monkeypatch.setattr(files_api, "workspace_setting", setting)
    return settings


def _client_factory(storage: ObjectStorageService):
    app = FastAPI()
    register_service_exception_handlers(app)
    app.include_router(files_api.router, prefix="/api/files")
    user = {"id": "member"}
    app.dependency_overrides[files_api.get_current_user_required] = lambda: SimpleNamespace(
        id=user["id"]
    )
    app.dependency_overrides[get_files_service] = lambda: FilesService(storage=storage)

    def as_(user_id: str) -> AsyncClient:
        user["id"] = user_id
        return AsyncClient(transport=ASGITransport(app=app), base_url="http://t")

    return as_


@pytest.fixture
def client(team, storage, drives):
    return _client_factory(storage)


def ws(**extra: str) -> dict[str, str]:
    return {"workspace_id": "ws-1", **extra}


@pytest.mark.asyncio
async def test_a_viewer_reads_the_workspace_drive_and_cannot_change_it(client, storage) -> None:
    async with client("viewer") as http:
        assert (await http.get("/api/files/", params=ws())).status_code == 200
        assert (await http.get("/api/files/readme.md", params=ws())).json()["content"] == "# one"
        assert (await http.get("/api/files/raw/readme.md", params=ws())).content == b"# one"
        archive = await http.get("/api/files/archive/docs", params=ws())
        assert archive.status_code == 200
        assert archive.headers["content-type"] == "application/zip"
        body = {"path": "new.md", "content": "x", "workspace_id": "ws-1"}
        assert (await http.post("/api/files/", json=body)).status_code == 403
        assert (await http.put("/api/files/readme.md", params=ws(), json=body)).status_code == 403
        assert (await http.delete("/api/files/readme.md", params=ws())).status_code == 403
        folder = {"path": "docs", "workspace_id": "ws-1"}
        assert (await http.post("/api/files/folder", json=folder)).status_code == 403
        rename = {"old_path": "readme.md", "new_path": "other.md", "workspace_id": "ws-1"}
        assert (await http.post("/api/files/rename", json=rename)).status_code == 403
        upload = await http.post(
            "/api/files/upload",
            data={"path": "", "workspace_id": "ws-1"},
            files={"file": ("up.txt", b"x", "text/plain")},
        )
        assert upload.status_code == 403
        assert (await http.post("/api/files/extract/a.zip", params=ws())).status_code == 403
    assert storage.get_object(WS1, "readme.md") == b"# one"


@pytest.mark.asyncio
async def test_a_member_writes_renames_and_deletes(client, storage) -> None:
    async with client("member") as http:
        body = {"path": "new.md", "content": "x", "workspace_id": "ws-1"}
        assert (await http.post("/api/files/", json=body)).status_code == 200
        assert storage.get_object(WS1, "new.md") == b"x"
        rename = {"old_path": "new.md", "new_path": "renamed.md", "workspace_id": "ws-1"}
        assert (await http.post("/api/files/rename", json=rename)).status_code == 200
        assert (await http.delete("/api/files/renamed.md", params=ws())).status_code == 200


@pytest.mark.asyncio
async def test_a_stranger_reaches_nothing_of_the_workspace(client) -> None:
    async with client("stranger") as http:
        assert (await http.get("/api/files/", params=ws())).status_code == 403
        assert (await http.get("/api/files/readme.md", params=ws())).status_code == 403
        body = {"path": "x.md", "content": "x", "workspace_id": "ws-1"}
        assert (await http.post("/api/files/", json=body)).status_code == 403


@pytest.mark.asyncio
async def test_no_member_of_one_workspace_reaches_another_workspaces_drive(client) -> None:
    async with client("owner") as http:
        # ws-2 is unknown to IAM: the owner of ws-1 holds nothing there.
        assert (
            await http.get("/api/files/secret.md", params={"workspace_id": "ws-2"})
        ).status_code == 403
        # A full storage path of ws-2 under ws-1's id is refused, and so is the
        # same path with no workspace id at all (the workspace is read from it).
        other = f"/api/files/{WS2}/secret.md"
        assert (await http.get(other, params=ws())).status_code == 400
        assert (await http.get(other)).status_code == 403
        assert (await http.get("/api/files/", params={"path": WS2})).status_code == 403
        # Traversal never gets as far as IAM.
        assert (await http.get("/api/files/..%2Fws-2%2Fsecret.md", params=ws())).status_code in (
            400,
            404,
        )


@pytest.mark.asyncio
async def test_the_system_drive_is_an_admins_and_needs_the_workspace_setting(
    client, drives
) -> None:
    system = {"scope": "system_drive", "workspace_id": "ws-1"}
    for user in ("viewer", "member", "stranger"):
        async with client(user) as http:
            assert (await http.get("/api/files/", params=system)).status_code == 403, user
            assert (await http.get(f"/api/files/{WS1}/readme.md", params=system)).status_code == 403
    async with client("admin") as http:
        assert (await http.get(f"/api/files/{WS1}/readme.md", params=system)).status_code == 200
        drives["system_drive_enabled"] = False
        off = await http.get(f"/api/files/{WS1}/readme.md", params=system)
        assert off.status_code == 403
        assert "not enabled" in off.json()["detail"]
    # An admin's write to the system drive is an admin action too.
    drives["system_drive_enabled"] = True
    body = {
        "path": f"{WS1}/sys.md",
        "content": "x",
        "workspace_id": "ws-1",
        "scope": "system_drive",
    }
    async with client("member") as http:
        assert (await http.post("/api/files/", json=body)).status_code == 403
    async with client("admin") as http:
        assert (await http.post("/api/files/", json=body)).status_code == 200


@pytest.mark.asyncio
async def test_the_platform_drive_is_read_by_viewers_written_by_members_when_enabled(
    client, drives, storage
) -> None:
    platform = {"scope": "platform_drive", "workspace_id": "ws-1"}
    async with client("viewer") as http:
        assert (await http.get("/api/files/shared.md", params=platform)).json()[
            "content"
        ] == "# shared"
        body = {"path": "x.md", "content": "x", "workspace_id": "ws-1", "scope": "platform_drive"}
        assert (await http.post("/api/files/", json=body)).status_code == 403
    async with client("member") as http:
        assert (await http.post("/api/files/", json=body)).status_code == 200
        drives["platform_drive_enabled"] = False
        off = await http.get("/api/files/shared.md", params=platform)
        assert off.status_code == 403
        assert "Platform drive is not enabled" in off.json()["detail"]
    async with client("stranger") as http:
        drives["platform_drive_enabled"] = True
        assert (await http.get("/api/files/shared.md", params=platform)).status_code == 403
    # The platform drive needs a workspace to be reached through.
    async with client("member") as http:
        assert (
            await http.get("/api/files/shared.md", params={"scope": "platform_drive"})
        ).status_code == 400


@pytest.mark.asyncio
async def test_my_drive_is_the_callers_own(client, storage) -> None:
    mine = {"scope": "my_drive"}
    async with client("viewer") as http:
        assert (await http.get("/api/files/mine.md", params=mine)).json()["content"] == "# viewer's"
        body = {"path": "x.md", "content": "x", "scope": "my_drive"}
        assert (await http.post("/api/files/", json=body)).status_code == 403
        # Another user's drive is never reachable by path: it lands inside the caller's own.
        other = "naas_abi/my-drive/member/mine.md"
        assert (await http.get(f"/api/files/{other}", params=mine)).status_code == 404
    async with client("member") as http:
        assert (await http.get("/api/files/mine.md", params=mine)).json()["content"] == "# member's"
        assert (await http.post("/api/files/", json=body)).status_code == 200
        assert storage.get_object("naas_abi/my-drive/member", "x.md") == b"x"
    async with client("stranger") as http:
        # Holding no role anywhere, a user has no drive to reach.
        assert (await http.get("/api/files/mine.md", params=mine)).status_code == 403


@pytest.mark.asyncio
async def test_a_role_without_the_files_feature_is_refused(storage, drives) -> None:
    everything = list(KNOWN_FEATURE_KEYS)
    flags = FeatureFlagsConfig(
        enabled_features=everything,
        role_baseline={
            "owner": everything,
            "admin": everything,
            "member": everything,
            "viewer": ["chat"],
        },
    )
    nexus = NexusIam(flags)
    scope = nexus.workspace("org-1", "ws-1")
    for user in ("member", "viewer"):
        nexus.grant(user, user, scope)
    with nexus.installed():
        client = _client_factory(storage)
        async with client("viewer") as http:
            denied = await http.get("/api/files/readme.md", params=ws())
            assert denied.status_code == 403
            assert "feature" in denied.json()["detail"]
        async with client("member") as http:
            assert (await http.get("/api/files/readme.md", params=ws())).status_code == 200
