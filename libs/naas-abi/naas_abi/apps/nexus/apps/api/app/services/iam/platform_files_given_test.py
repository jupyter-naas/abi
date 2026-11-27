"""Platform Files given by a workspace (Settings › Files, through
``/api/workspaces/{id}/offer`` and ``/offer/files``): read by the workspace's admins as its
configuration, given by the platform admin alone (IAM decides: a write of "<W> access"
whose ``GivenPlatformFiles`` is held-checked), narrowed by the workspace's admin. And
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
from naas_abi.apps.nexus.apps.api.app.services.feature_access.adapters.primary.feature_access__primary_adapter__FastAPI import (  # noqa: E501
    router,
)
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
from naas_abi.apps.nexus.apps.api.app.services.iam.testing import NexusIam
from naas_abi.apps.nexus.apps.api.app.services.iam.workspace_offer import Offer, offer_of
from naas_abi.apps.nexus.apps.api.app.services.iam_admin.adapters.secondary.engine import (
    EngineIamGateway,
)
from naas_abi.apps.nexus.apps.api.app.services.iam_admin.testing import MemoryAudit
from naas_abi_core.engine.call_context import as_service_account, use_call_context

OFFER = "/api/workspaces/ws-1/offer"
PATH = f"{OFFER}/files"


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


def _platform(offer: dict) -> dict:
    """The Platform Files row of an offer state: ``{mode, editable}``."""
    row = next(r for r in offer["files"] if r["key"] == "platform_files")
    return {"mode": row["mode"], "editable": row["editable"]}


def _give(client, user: str, mode: str):
    return client.put(PATH, json={"platform_files": mode}, headers=_as(user))


@pytest.mark.asyncio
async def test_the_workspace_admins_read_it_off_and_may_not_change_it(client):
    for user in ("wadmin", "oadmin"):
        found = client.get(OFFER, headers=_as(user))
        assert found.status_code == 200, user
        assert _platform(found.json()) == {"mode": "off", "editable": False}
    for user in ("member", "stranger"):
        assert client.get(OFFER, headers=_as(user)).status_code in (403, 404), user


@pytest.mark.asyncio
async def test_only_the_platform_admin_changes_it(client, world):
    for user in ("wadmin", "oadmin", "member"):
        refused = _give(client, user, "write")
        # A member may not even read "<W> access": not found.
        assert refused.status_code in ((403, 404) if user == "member" else (403,)), user
    assert _given(world) is None

    assert _platform(client.get(OFFER, headers=_as("root")).json())["editable"] is True
    saved = _give(client, "root", "write")
    assert saved.status_code == 200
    assert _platform(saved.json()) == {"mode": "write", "editable": True}
    assert _platform(client.get(OFFER, headers=_as("wadmin")).json())["mode"] == "write"

    assert _given(world) == "write"
    # The workspace's admin may narrow it, never widen it back.
    narrowed = _give(client, "wadmin", "read")
    assert _platform(narrowed.json()) == {"mode": "read", "editable": True}
    assert _give(client, "wadmin", "write").status_code == 403
    assert _platform(_give(client, "root", "off").json())["mode"] == "off"


def _given(world) -> str | None:
    with as_service_account("api"):
        return offer_of(world.iam.get_policy(world.alpha.access_policy_id).document).platform_files


@pytest.mark.asyncio
async def test_a_bad_mode_or_an_unknown_workspace_is_refused(client):
    assert _give(client, "root", "all").status_code == 422
    unknown = client.put(
        "/api/workspaces/ws-404/offer/files", json={"platform_files": "read"}, headers=_as("root")
    )
    assert unknown.status_code == 404


def _views(client, user: str) -> list[str]:
    found = client.get("/api/files/views", params={"workspace_id": "ws-1"}, headers=_as(user))
    assert found.status_code == 200
    return [view["id"] for view in found.json()["views"]]


@pytest.mark.asyncio
async def test_the_files_views_list_platform_files_for_the_workspaces_people(client, world):
    assert "platform_files" not in _views(client, "member")

    _give(client, "root", "read")

    assert "platform_files" in _views(client, "member")
    assert "platform_files" in _views(client, "wadmin")
    assert "platform_files" not in _views(client, "stranger")


@pytest.mark.asyncio
async def test_may_use_platform_files_is_the_supported_check_for_a_module(client, world):
    assert await may_use_platform_files("member") is False

    _give(client, "root", "write")

    with use_call_context(NexusIam.context(None)):
        assert await may_use_platform_files("member") is True
        assert await may_use_platform_files("stranger") is False
