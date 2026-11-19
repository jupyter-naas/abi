"""The files router decides with IAM alone: viewers read, members write, nobody leaves
their workspace's drive, Platform Files is nobody's until a policy grants it and
System Files is the platform admin's.

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
from naas_abi.apps.nexus.apps.api.app.services.iam.testing import NexusIam
from naas_abi_core.engine.call_context import as_service_account
from naas_abi_core.services.iam.IAMService import LEGACY_NEXUS_ISSUER
from naas_abi_core.services.object_storage.adapters.secondary.ObjectStorageSecondaryAdapterFS import (  # noqa: E501
    ObjectStorageSecondaryAdapterFS,
)
from naas_abi_core.services.object_storage.ObjectStorageService import ObjectStorageService

WS1 = "naas_abi/workspace-drive/ws-1"
WS2 = "naas_abi/workspace-drive/ws-2"


@pytest.fixture(autouse=True)
def _nothing_placed() -> None:
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
def client(team, storage):
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


ROLES = ("viewer", "member", "admin", "owner")


def _platform_grant(team: NexusIam, user_id: str, actions: list[str], resources: list[str]) -> None:
    """A policy attached to ``user_id`` at the platform: what a platform admin grants."""
    with as_service_account("engine"):
        principal = team.iam.ensure_user(LEGACY_NEXUS_ISSUER, user_id, provider="nexus")
        policy = team.iam.create_policy(
            f"platform-{user_id}-{len(actions)}",
            {
                "version": "2026-10-13",
                "statements": [{"effect": "Allow", "actions": actions, "resources": resources}],
            },
        )
        team.iam.attach_policy(policy.id, principal.id)


PLATFORM_FILES = {"scope": "platform_drive"}


def platform_body(path: str) -> dict[str, str]:
    return {"path": path, "content": "x", "scope": "platform_drive"}


@pytest.mark.asyncio
async def test_platform_files_are_refused_to_every_role(client) -> None:
    """No role reaches Platform Files, owners included, through any workspace."""
    for user in (*ROLES, "stranger"):
        async with client(user) as http:
            for params in (PLATFORM_FILES, {**PLATFORM_FILES, "workspace_id": "ws-1"}):
                assert (await http.get("/api/files/", params=params)).status_code == 403, user
                read = await http.get("/api/files/shared.md", params=params)
                assert read.status_code == 403, user
            assert (await http.post("/api/files/", json=platform_body("x.md"))).status_code == 403


@pytest.mark.asyncio
async def test_a_policy_at_the_platform_opens_platform_files(client, team, storage) -> None:
    """Granted at the platform, decided at the platform: no workspace is needed."""
    _platform_grant(
        team,
        "viewer",
        ["nexus:ListPlatformFiles", "nexus:GetPlatformFile"],
        ["abi:nexus:platform_file/*"],
    )
    async with client("viewer") as http:
        listing = await http.get("/api/files/", params=PLATFORM_FILES)
        assert listing.status_code == 200
        assert "shared.md" in {f["name"] for f in listing.json()["files"]}
        read = await http.get("/api/files/shared.md", params=PLATFORM_FILES)
        assert read.json()["content"] == "# shared"
        # Reading is not writing.
        assert (await http.post("/api/files/", json=platform_body("x.md"))).status_code == 403
    _platform_grant(
        team,
        "member",
        ["nexus:PutPlatformFile", "nexus:DeletePlatformFile"],
        ["abi:nexus:platform_file/platform/shared/*"],
    )
    async with client("member") as http:
        assert (
            await http.post("/api/files/", json=platform_body("shared/new.md"))
        ).status_code == 200
        assert storage.get_object("naas_abi/platform-drive/shared", "new.md") == b"x"
        # Only the folder it was granted.
        assert (await http.post("/api/files/", json=platform_body("other.md"))).status_code == 403
        # Writing is not reading.
        assert (await http.get("/api/files/shared.md", params=PLATFORM_FILES)).status_code == 403


@pytest.mark.asyncio
async def test_the_platform_admin_holds_platform_and_system_files(client, team, storage) -> None:
    team.platform_admin("root")
    async with client("root") as http:
        read = await http.get("/api/files/shared.md", params=PLATFORM_FILES)
        assert read.json()["content"] == "# shared"
        assert (await http.post("/api/files/", json=platform_body("root.md"))).status_code == 200
        system = {"scope": "system_drive"}
        listing = await http.get("/api/files/", params=system)
        assert listing.status_code == 200
        assert "naas_abi" in {f["name"] for f in listing.json()["files"]}
        assert (await http.get(f"/api/files/{WS2}/secret.md", params=system)).json()[
            "content"
        ] == "# two"
        body = {"path": f"{WS1}/sys.md", "content": "x", "scope": "system_drive"}
        assert (await http.post("/api/files/", json=body)).status_code == 200
    assert storage.get_object(WS1, "sys.md") == b"x"


@pytest.mark.asyncio
async def test_system_files_are_refused_to_workspace_owners_and_admins(client) -> None:
    system = {"scope": "system_drive", "workspace_id": "ws-1"}
    body = {
        "path": f"{WS1}/sys.md",
        "content": "x",
        "workspace_id": "ws-1",
        "scope": "system_drive",
    }
    for user in (*ROLES, "stranger"):
        async with client(user) as http:
            assert (await http.get("/api/files/", params=system)).status_code == 403, user
            assert (await http.get(f"/api/files/{WS1}/readme.md", params=system)).status_code == 403
            assert (await http.post("/api/files/", json=body)).status_code == 403, user


@pytest.mark.asyncio
async def test_the_old_system_file_actions_authorize_nothing(client, team) -> None:
    """``ListSystemFiles`` and its siblings stay declared (a policy may still name
    them) but open nothing: System Files is decided at the platform."""
    team.allow(
        "admin",
        ["nexus:ListSystemFiles", "nexus:GetSystemFile", "nexus:PutSystemFile"],
        ["${scope}/nexus:file/system", "${scope}/nexus:file/system/*"],
        team.workspace("org-1", "ws-1"),
    )
    system = {"scope": "system_drive", "workspace_id": "ws-1"}
    async with client("admin") as http:
        assert (await http.get("/api/files/", params=system)).status_code == 403
        assert (await http.get(f"/api/files/{WS1}/readme.md", params=system)).status_code == 403


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
async def test_a_role_without_the_files_feature_is_refused(storage) -> None:
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


# -- The organization drive ------------------------------------------------------

ORG1 = "naas_abi/organization-drive/org-1"
ORG2 = "naas_abi/organization-drive/org-2"


@pytest.fixture
def org_storage(storage) -> ObjectStorageService:
    storage.put_object(ORG1, "policy.md", b"# org-1 policy")
    storage.put_object(f"{ORG1}/operations", "plan.md", b"# ops")
    storage.put_object(ORG2, "secret.md", b"# org-2")
    return storage


def org(**extra: str) -> dict[str, str]:
    return {"scope": "organization_drive", "workspace_id": "ws-1", **extra}


def org_body(path: str, workspace_id: str = "ws-1") -> dict[str, str]:
    return {
        "path": path,
        "content": "x",
        "workspace_id": workspace_id,
        "scope": "organization_drive",
    }


@pytest.mark.asyncio
async def test_the_organization_drive_is_read_by_its_people_and_written_by_its_admins(
    client, org_storage
) -> None:
    for user in ("viewer", "member", "admin", "owner"):
        async with client(user) as http:
            listing = await http.get("/api/files/", params=org())
            assert listing.status_code == 200, user
            assert {f["name"] for f in listing.json()["files"]} >= {"policy.md", "operations"}
            read = await http.get("/api/files/policy.md", params=org())
            assert read.json()["content"] == "# org-1 policy", user
    for user in ("viewer", "member"):
        async with client(user) as http:
            assert (await http.post("/api/files/", json=org_body("x.md"))).status_code == 403
            assert (await http.delete("/api/files/policy.md", params=org())).status_code == 403
    for user in ("admin", "owner"):
        async with client(user) as http:
            assert (await http.post("/api/files/", json=org_body(f"{user}.md"))).status_code == 200
            assert org_storage.get_object(ORG1, f"{user}.md") == b"x"
            assert (await http.delete(f"/api/files/{user}.md", params=org())).status_code == 200


@pytest.mark.asyncio
async def test_a_stranger_and_a_workspace_in_no_organization_reach_no_organization_drive(
    client, team, org_storage
) -> None:
    async with client("stranger") as http:
        assert (await http.get("/api/files/policy.md", params=org())).status_code == 403
    solo = team.workspace(None, "ws-solo")
    team.grant("member", "member", solo)
    async with client("member") as http:
        none = await http.get("/api/files/", params=org(workspace_id="ws-solo"))
        assert none.status_code == 404
        assert "no organization" in none.json()["detail"]
        # The drive is reached through a workspace.
        no_ws = await http.get("/api/files/", params={"scope": "organization_drive"})
        assert no_ws.status_code == 400


@pytest.mark.asyncio
async def test_a_workspace_reaches_its_own_organizations_drive_alone(
    client, team, org_storage
) -> None:
    other = team.workspace("org-2", "ws-2")
    team.grant("other", "member", other)
    team.grant("other", "member", team.org("org-2"))
    async with client("other") as http:
        # Its own organization's drive.
        own = await http.get("/api/files/secret.md", params=org(workspace_id="ws-2"))
        assert own.json()["content"] == "# org-2"
        # Not org-1's, through org-1's workspace...
        assert (await http.get("/api/files/policy.md", params=org())).status_code == 403
        # ...nor by naming org-1's drive from its own workspace: the path stays inside org-2's.
        named = await http.get(f"/api/files/{ORG1}/policy.md", params=org(workspace_id="ws-2"))
        assert named.status_code == 404
    async with client("owner") as http:
        # An owner of org-1 holds nothing in org-2.
        assert (
            await http.get("/api/files/secret.md", params=org(workspace_id="ws-2"))
        ).status_code == 403


@pytest.mark.asyncio
async def test_a_policy_at_the_organization_lets_members_write_one_folder(
    client, team, org_storage
) -> None:
    team.allow(
        "member",
        ["nexus:PutOrgFile", "nexus:DeleteOrgFile"],
        ["${scope}/nexus:file/organization/operations/*"],
        team.org("org-1"),
    )
    async with client("member") as http:
        assert (
            await http.post("/api/files/", json=org_body("operations/new.md"))
        ).status_code == 200
        assert org_storage.get_object(f"{ORG1}/operations", "new.md") == b"x"
        assert (await http.post("/api/files/", json=org_body("finance/x.md"))).status_code == 403
        assert (await http.post("/api/files/", json=org_body("x.md"))).status_code == 403


@pytest.mark.asyncio
async def test_a_deny_at_the_organization_hides_a_folder(client, team, org_storage) -> None:
    org_storage.put_object(f"{ORG1}/finance", "budget.md", b"# budget")
    team.deny(
        "member",
        ["nexus:ListOrgFiles", "nexus:GetOrgFile"],
        ["${scope}/nexus:file/organization/finance", "${scope}/nexus:file/organization/finance/*"],
        team.org("org-1"),
    )
    async with client("member") as http:
        assert (await http.get("/api/files/finance/budget.md", params=org())).status_code == 403
        assert (await http.get("/api/files/", params=org(path="finance"))).status_code == 403
        assert (await http.get("/api/files/policy.md", params=org())).status_code == 200
    async with client("viewer") as http:
        assert (await http.get("/api/files/finance/budget.md", params=org())).status_code == 200


@pytest.mark.asyncio
async def test_the_organization_drive_keeps_its_system_files_read_only(client, org_storage) -> None:
    async with client("owner") as http:
        assert (await http.post("/api/files/", json=org_body(".manifest.json"))).status_code == 403
