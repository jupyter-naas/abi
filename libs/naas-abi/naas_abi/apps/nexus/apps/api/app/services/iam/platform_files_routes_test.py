"""``/api/workspaces/{id}/platform-files``: read by the workspace's admins as its
configuration, given by the platform admin alone (IAM decides: a write of "<W> access"
whose ``GivenPlatformFiles`` is held-checked), 403 for everyone else. And
``GET /api/files/views`` lists Platform Files for the people of a workspace that gives
it, decided as the files routes decide it (``may_use_platform_files``)."""

from __future__ import annotations

from types import SimpleNamespace

import pytest
import pytest_asyncio
from fastapi import FastAPI, HTTPException, Request
from fastapi.testclient import TestClient
from naas_abi.apps.nexus.apps.api.app.services.auth.adapters.primary.auth__primary_adapter__dependencies import (  # noqa: E501
    get_current_user_required,
)
from naas_abi.apps.nexus.apps.api.app.services.feature_access import runtime as offers_runtime
from naas_abi.apps.nexus.apps.api.app.services.feature_access.service import (
    FeatureAccessService,
)
from naas_abi.apps.nexus.apps.api.app.services.files.adapters.primary.files__primary_adapter__dependencies import (  # noqa: E501
    may_use_platform_files,
)
from naas_abi.apps.nexus.apps.api.app.services.files.adapters.primary.files__primary_adapter__FastAPI import (  # noqa: E501
    router as files_router,
)
from naas_abi.apps.nexus.apps.api.app.services.iam.authz import AUTHZ
from naas_abi.apps.nexus.apps.api.app.services.iam.container_defaults import CONTAINER_DEFAULTS
from naas_abi.apps.nexus.apps.api.app.services.iam.memberships import MEMBERSHIPS
from naas_abi.apps.nexus.apps.api.app.services.iam.names import org_container
from naas_abi.apps.nexus.apps.api.app.services.iam.platform_files_routes import router
from naas_abi.apps.nexus.apps.api.app.services.iam.testing import NexusIam
from naas_abi.apps.nexus.apps.api.app.services.iam.workspace_offer import Offer, offer_of
from naas_abi.apps.nexus.apps.api.app.services.iam_admin.adapters.secondary.engine import (
    EngineIamGateway,
)
from naas_abi.apps.nexus.apps.api.app.services.iam_admin.testing import MemoryAudit
from naas_abi_core.engine.call_context import as_service_account, use_call_context

PATH = "/api/workspaces/ws-1/platform-files"


def _by_header(request: Request) -> SimpleNamespace:
    user = request.headers.get("x-user")
    if not user:
        raise HTTPException(401, "Not authenticated")
    return SimpleNamespace(id=user, email=f"{user}@example.com", name=user)


@pytest.fixture
def world():
    nexus = NexusIam(features_with_roles=False)
    with nexus.installed():
        nexus.grouped_org("org-1", "Acme")
        alpha = nexus.grouped_workspace(
            "org-1", "ws-1", "Alpha", offer=Offer.of(features=["files", "chat"])
        )
        for person in ("member", "wadmin", "oadmin", "stranger"):
            nexus.user(person)
        nexus.platform_admin("root")
        nexus.W = alpha.container  # type: ignore[attr-defined]
        nexus.alpha = alpha  # type: ignore[attr-defined]
        previous = offers_runtime.configure(
            lambda: FeatureAccessService(
                EngineIamGateway(),
                None,  # type: ignore[arg-type]
                MemoryAudit(),
                container_of=AUTHZ.container_of,
                defaults_of=CONTAINER_DEFAULTS.record_of,
                features=lambda: ["files", "chat"],
            )
        )
        try:
            yield nexus
        finally:
            offers_runtime.configure(previous)


@pytest_asyncio.fixture
async def client(world):
    await MEMBERSHIPS.grant("oadmin", "admin", org_container("org-1"))
    await MEMBERSHIPS.grant("member", "member", world.W)
    await MEMBERSHIPS.grant("wadmin", "admin", world.W)
    app = FastAPI()
    app.include_router(router, prefix="/api/workspaces")
    app.include_router(files_router, prefix="/api/files")
    app.dependency_overrides[get_current_user_required] = _by_header
    return TestClient(app)


def _as(user: str) -> dict[str, str]:
    return {"x-user": user}


@pytest.mark.asyncio
async def test_the_workspace_admins_read_it_off_and_may_not_change_it(client):
    for user in ("wadmin", "oadmin"):
        found = client.get(PATH, headers=_as(user))
        assert found.status_code == 200, user
        assert found.json() == {"workspace_id": "ws-1", "mode": "off", "can_change": False}
    for user in ("member", "stranger"):
        assert client.get(PATH, headers=_as(user)).status_code in (403, 404), user


@pytest.mark.asyncio
async def test_only_the_platform_admin_changes_it(client, world):
    for user in ("wadmin", "oadmin", "member"):
        refused = client.put(PATH, json={"mode": "write"}, headers=_as(user))
        # A member may not even read "<W> access": not found.
        assert refused.status_code in ((403, 404) if user == "member" else (403,)), user
    assert _given(world) is None

    assert client.get(PATH, headers=_as("root")).json()["can_change"] is True
    saved = client.put(PATH, json={"mode": "write"}, headers=_as("root"))
    assert saved.status_code == 200
    assert saved.json() == {"workspace_id": "ws-1", "mode": "write", "can_change": True}
    assert client.get(PATH, headers=_as("wadmin")).json()["mode"] == "write"

    assert _given(world) == "write"
    # The workspace's admin may narrow it, never widen it back.
    narrowed = client.put(PATH, json={"mode": "read"}, headers=_as("wadmin"))
    assert narrowed.json() == {"workspace_id": "ws-1", "mode": "read", "can_change": True}
    assert client.put(PATH, json={"mode": "write"}, headers=_as("wadmin")).status_code == 403
    assert client.put(PATH, json={"mode": "off"}, headers=_as("root")).json()["mode"] == "off"


def _given(world) -> str | None:
    with as_service_account("api"):
        return offer_of(world.iam.get_policy(world.alpha.access_policy_id).document).platform_files


@pytest.mark.asyncio
async def test_a_bad_mode_or_an_unknown_workspace_is_refused(client):
    assert client.put(PATH, json={"mode": "all"}, headers=_as("root")).status_code == 422
    unknown = client.put(
        "/api/workspaces/ws-404/platform-files", json={"mode": "read"}, headers=_as("root")
    )
    assert unknown.status_code == 404


def _views(client, user: str) -> list[str]:
    found = client.get("/api/files/views", params={"workspace_id": "ws-1"}, headers=_as(user))
    assert found.status_code == 200
    return [view["id"] for view in found.json()["views"]]


@pytest.mark.asyncio
async def test_the_files_views_list_platform_files_for_the_workspaces_people(client, world):
    assert "platform_files" not in _views(client, "member")

    client.put(PATH, json={"mode": "read"}, headers=_as("root"))

    assert "platform_files" in _views(client, "member")
    assert "platform_files" in _views(client, "wadmin")
    assert "platform_files" not in _views(client, "stranger")


@pytest.mark.asyncio
async def test_may_use_platform_files_is_the_supported_check_for_a_module(client, world):
    assert await may_use_platform_files("member") is False

    client.put(PATH, json={"mode": "write"}, headers=_as("root"))

    with use_call_context(NexusIam.context(None)):
        assert await may_use_platform_files("member") is True
        assert await may_use_platform_files("stranger") is False
