"""``GET /api/files/views``: the views of the file system the caller may open in a
workspace, IAM's answer alone (no workspace flag).

The real router over a real IAM (``team``: ``ws-1`` of ``org-1`` with an owner, an
admin, a member and a viewer, plus a stranger).
"""

from __future__ import annotations

from types import SimpleNamespace

import pytest
from fastapi import FastAPI
from httpx import ASGITransport, AsyncClient
from naas_abi.apps.nexus.apps.api.app.core.config import FeatureFlagsConfig
from naas_abi.apps.nexus.apps.api.app.core.feature_flags import KNOWN_FEATURE_KEYS
from naas_abi.apps.nexus.apps.api.app.services.files.adapters.primary import (
    files__primary_adapter__FastAPI as files_api,
)
from naas_abi.apps.nexus.apps.api.app.services.iam.testing import NexusIam
from naas_abi_core.engine.call_context import as_service_account
from naas_abi_core.services.iam.IAMService import LEGACY_NEXUS_ISSUER

ROLES = ("viewer", "member", "admin", "owner")


def _client_factory():
    app = FastAPI()
    app.include_router(files_api.router, prefix="/api/files")
    user = {"id": "member"}
    app.dependency_overrides[files_api.get_current_user_required] = lambda: SimpleNamespace(
        id=user["id"]
    )

    def as_(user_id: str) -> AsyncClient:
        user["id"] = user_id
        return AsyncClient(transport=ASGITransport(app=app), base_url="http://t")

    return as_


@pytest.fixture
def client(team):
    return _client_factory()


async def _views(client, user: str, **params: str) -> list[dict]:
    async with client(user) as http:
        response = await http.get("/api/files/views", params=params)
    assert response.status_code == 200, response.text
    return response.json()["views"]


def _ids(views: list[dict]) -> list[str]:
    return [view["id"] for view in views]


def _grant_platform_files(team: NexusIam, user_id: str) -> None:
    with as_service_account("engine"):
        principal = team.iam.ensure_user(LEGACY_NEXUS_ISSUER, user_id, provider="nexus")
        policy = team.iam.create_policy(
            f"platform-files-{user_id}",
            {
                "version": "2026-10-13",
                "statements": [
                    {
                        "effect": "Allow",
                        "actions": ["nexus:ListPlatformFiles", "nexus:GetPlatformFile"],
                        "resources": ["abi:nexus:platform_file/*"],
                    }
                ],
            },
        )
        team.iam.attach_policy(policy.id, principal.id)


@pytest.mark.asyncio
async def test_every_role_opens_its_own_workspaces_and_organizations_views(client) -> None:
    for user in ROLES:
        views = await _views(client, user, workspace_id="ws-1")
        assert _ids(views) == ["my_files", "workspace_files", "organization_files"], user


@pytest.mark.asyncio
async def test_each_view_names_its_scope_and_root(client, team) -> None:
    team.platform_admin("root")
    views = {view["id"]: view for view in await _views(client, "root", workspace_id="ws-1")}
    assert views == {
        "my_files": {
            "id": "my_files",
            "label": "My Files",
            "drive": "file_system",
            "scope": "my_drive",
            "root": "naas_abi/my-drive/root",
        },
        "workspace_files": {
            "id": "workspace_files",
            "label": "Workspace Files",
            "drive": "file_system",
            "scope": "workspace",
            "root": "naas_abi/workspace-drive/ws-1",
        },
        "organization_files": {
            "id": "organization_files",
            "label": "Organization Files",
            "drive": "file_system",
            "scope": "organization_drive",
            "root": "naas_abi/organization-drive/org-1",
        },
        "platform_files": {
            "id": "platform_files",
            "label": "Platform Files",
            "drive": "file_system",
            "scope": "platform_drive",
            "root": "naas_abi/platform-drive",
        },
        "system_files": {
            "id": "system_files",
            "label": "System Files",
            "drive": "file_system",
            "scope": "system_drive",
            "root": "",
        },
    }


@pytest.mark.asyncio
async def test_the_platform_admin_opens_every_view_in_order(client, team) -> None:
    team.platform_admin("root")
    assert _ids(await _views(client, "root", workspace_id="ws-1")) == [
        "my_files",
        "workspace_files",
        "organization_files",
        "platform_files",
        "system_files",
    ]


@pytest.mark.asyncio
async def test_platform_files_are_listed_to_who_a_policy_grants_them(client, team) -> None:
    assert "platform_files" not in _ids(await _views(client, "member", workspace_id="ws-1"))
    _grant_platform_files(team, "member")
    assert _ids(await _views(client, "member", workspace_id="ws-1")) == [
        "my_files",
        "workspace_files",
        "organization_files",
        "platform_files",
    ]
    # Decided at the platform: listed without a workspace too.
    assert _ids(await _views(client, "member")) == ["my_files", "platform_files"]


@pytest.mark.asyncio
async def test_a_stranger_opens_nothing(client) -> None:
    assert await _views(client, "stranger", workspace_id="ws-1") == []
    assert await _views(client, "stranger") == []


@pytest.mark.asyncio
async def test_without_a_workspace_only_the_views_of_no_workspace_are_listed(client) -> None:
    assert _ids(await _views(client, "member")) == ["my_files"]
    # A workspace IAM does not know opens none of its views.
    assert _ids(await _views(client, "member", workspace_id="ws-unknown")) == ["my_files"]


@pytest.mark.asyncio
async def test_a_workspace_in_no_organization_has_no_organization_view(client, team) -> None:
    solo = team.workspace(None, "ws-solo")
    team.grant("member", "member", solo)
    assert _ids(await _views(client, "member", workspace_id="ws-solo")) == [
        "my_files",
        "workspace_files",
    ]


@pytest.mark.asyncio
async def test_a_role_without_the_files_feature_opens_no_workspace_view() -> None:
    everything = list(KNOWN_FEATURE_KEYS)
    flags = FeatureFlagsConfig(
        enabled_features=everything,
        role_baseline={"owner": everything, "member": everything, "viewer": ["chat"]},
    )
    nexus = NexusIam(flags)
    scope = nexus.workspace("org-1", "ws-1")
    for user in ("member", "viewer"):
        nexus.grant(user, user, scope)
        nexus.grant(user, user, nexus.org("org-1"))
    with nexus.installed():
        client = _client_factory()
        assert _ids(await _views(client, "viewer", workspace_id="ws-1")) == ["my_files"]
        assert _ids(await _views(client, "member", workspace_id="ws-1")) == [
            "my_files",
            "workspace_files",
            "organization_files",
        ]


@pytest.mark.asyncio
async def test_a_view_as_session_lists_neither_my_files_nor_system_files(
    client, team, monkeypatch
) -> None:
    """In a view of another person's workspace (``view_as``), My Files and System Files
    are not shown, as the files routes refuse them there."""
    team.platform_admin("root")
    monkeypatch.setattr(files_api, "viewing", lambda: True)
    assert _ids(await _views(client, "root", workspace_id="ws-1")) == [
        "workspace_files",
        "organization_files",
        "platform_files",
    ]
