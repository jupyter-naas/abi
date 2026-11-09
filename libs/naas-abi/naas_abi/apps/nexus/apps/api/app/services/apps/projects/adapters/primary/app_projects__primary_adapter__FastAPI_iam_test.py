"""Who may list, read, edit, preview and submit app projects: IAM decides, on the real router."""

from __future__ import annotations

from pathlib import Path
from types import SimpleNamespace

import pytest
from fastapi import FastAPI
from httpx import ASGITransport, AsyncClient
from naas_abi.apps.nexus.apps.api.app.core.config import FeatureFlagsConfig
from naas_abi.apps.nexus.apps.api.app.services.apps.projects.adapters.primary import (
    app_projects__primary_adapter__FastAPI as adapter,
)
from naas_abi.apps.nexus.apps.api.app.services.apps.projects.adapters.secondary.object_storage import (
    AppDraftStoreObjectStorage,
)
from naas_abi.apps.nexus.apps.api.app.services.apps.projects.adapters.secondary.source_control import (
    AppProjectRepositoryGit,
)
from naas_abi.apps.nexus.apps.api.app.services.apps.projects.placement import (
    draft_placement,
)
from naas_abi.apps.nexus.apps.api.app.services.apps.projects.service import (
    AppProjectsService,
)
from naas_abi.apps.nexus.apps.api.app.services.auth import credentials
from naas_abi.apps.nexus.apps.api.app.services.auth.adapters.primary.auth__primary_adapter__dependencies import (  # noqa: E501
    get_current_user_required,
)
from naas_abi.apps.nexus.apps.api.app.services.iam.names import workspace_container
from naas_abi.apps.nexus.apps.api.app.services.iam.testing import NexusIam
from naas_abi_core.engine.call_context import current_call_context
from naas_abi_core.services.iam.names import PLATFORM, encode_id
from naas_abi_core.services.object_storage.adapters.secondary.ObjectStorageSecondaryAdapterFS import (
    ObjectStorageSecondaryAdapterFS,
)
from naas_abi_core.services.object_storage.ObjectStorageService import (
    ObjectStorageService,
)
from naas_abi_core.services.source_control.adapters.secondary.InMemoryAdapter import (
    InMemoryAdapter,
)
from naas_abi_core.services.source_control.SourceControlService import (
    SourceControlService,
)

BASE = "/api/app-projects"
WS = {"workspace_id": "ws-1"}


@pytest.fixture
def world(tmp_path: Path):
    # Every role holds the apps section, so only the action's level decides.
    flags = FeatureFlagsConfig(
        enabled_features=["apps", "chat"],
        role_baseline={role: ["apps", "chat"] for role in ("owner", "admin", "member", "viewer")},
    )
    nexus = NexusIam(flags)
    scope = nexus.workspace("org-1", "ws-1")
    nexus.workspace("org-1", "ws-2")
    for user in ("owner", "admin", "member", "viewer"):
        nexus.grant(user, user, scope)
    nexus.user("stranger")

    sc = SourceControlService(InMemoryAdapter())
    sc.ensure_repo(owner="abi", name="monorepo")
    service = AppProjectsService(
        repository=AppProjectRepositoryGit(sc, "abi/monorepo"),
        drafts=AppDraftStoreObjectStorage(
            ObjectStorageService(ObjectStorageSecondaryAdapterFS(str(tmp_path)))
        ),
    )
    app = FastAPI()
    app.include_router(adapter.router, prefix=BASE)
    app.dependency_overrides[adapter.get_app_projects_service] = lambda: service
    user = {"id": "member"}
    app.dependency_overrides[get_current_user_required] = lambda: SimpleNamespace(
        id=user["id"], email=f"{user['id']}@example.com", name=user["id"]
    )

    def as_(user_id: str) -> AsyncClient:
        user["id"] = user_id
        return AsyncClient(transport=ASGITransport(app=app), base_url="http://t")

    # A preview link is a grant IAM stores: the same IAM makes it.
    previous = credentials.configure_iam(lambda: nexus.iam)
    try:
        with nexus.installed():
            yield SimpleNamespace(as_=as_, nexus=nexus, service=service)
    finally:
        credentials.configure_iam(previous)


async def _create(world, user: str = "member", title: str = "Budget") -> str:
    async with world.as_(user) as http:
        created = await http.post(f"{BASE}/", json={**WS, "title": title})
        assert created.status_code == 200, created.text
        return created.json()["slug"]


@pytest.mark.asyncio
async def test_a_viewer_reads_and_previews_but_cannot_change_a_project(world) -> None:
    slug = await _create(world)
    async with world.as_("viewer") as http:
        assert (await http.get(f"{BASE}/", params=WS)).status_code == 200
        assert (await http.get(f"{BASE}/submit-config", params=WS)).status_code == 200
        assert (await http.get(f"{BASE}/{slug}", params=WS)).status_code == 200
        file = await http.get(f"{BASE}/{slug}/file", params={**WS, "path": "index.html"})
        assert file.status_code == 200
        assert (await http.get(f"{BASE}/{slug}/history", params=WS)).status_code == 200
        assert (await http.get(f"{BASE}/{slug}/check", params=WS)).status_code == 200
        assert (await http.post(f"{BASE}/{slug}/preview-token", json=WS)).status_code == 200

        assert (await http.post(f"{BASE}/", json={**WS, "title": "New"})).status_code == 403
        assert (
            await http.post(f"{BASE}/import", json={**WS, "app_id": "acme.ops:map"})
        ).status_code == 403
        assert (await http.patch(f"{BASE}/{slug}", json={**WS, "title": "x"})).status_code == 403
        written = await http.put(
            f"{BASE}/{slug}/file", json={**WS, "path": "a.css", "content": "h1{}"}
        )
        assert written.status_code == 403
        deleted = await http.delete(f"{BASE}/{slug}/file", params={**WS, "path": "index.html"})
        assert deleted.status_code == 403
        assert (await http.post(f"{BASE}/{slug}/save", json=WS)).status_code == 403
        assert (await http.post(f"{BASE}/{slug}/discard", json=WS)).status_code == 403
        assert (await http.post(f"{BASE}/{slug}/submit", json=WS)).status_code == 403
    # Nothing a viewer sent reached the project.
    async with world.as_("member") as http:
        project = (await http.get(f"{BASE}/{slug}", params=WS)).json()
        assert {f["path"] for f in project["files"]} >= {"index.html"}
        assert "a.css" not in {f["path"] for f in project["files"]}


@pytest.mark.asyncio
async def test_a_member_edits_saves_and_submits(world) -> None:
    slug = await _create(world)
    async with world.as_("member") as http:
        written = await http.put(
            f"{BASE}/{slug}/file", json={**WS, "path": "a.css", "content": "h1{}"}
        )
        assert written.status_code == 200
        assert (
            await http.patch(f"{BASE}/{slug}", json={**WS, "title": "Renamed"})
        ).status_code == 200
        assert (await http.post(f"{BASE}/{slug}/save", json=WS)).json()["saved"] is True
        deleted = await http.delete(f"{BASE}/{slug}/file", params={**WS, "path": "a.css"})
        assert deleted.json() == {"deleted": True}
        assert (await http.post(f"{BASE}/{slug}/discard", json=WS)).status_code == 200
        # Authorized: the 409 is the deployment having no submit repository.
        assert (await http.post(f"{BASE}/{slug}/submit", json=WS)).status_code == 409


@pytest.mark.asyncio
async def test_a_stranger_reaches_nothing(world) -> None:
    slug = await _create(world)
    async with world.as_("stranger") as http:
        for response in (
            await http.get(f"{BASE}/", params=WS),
            await http.get(f"{BASE}/submit-config", params=WS),
            await http.get(f"{BASE}/{slug}", params=WS),
            await http.get(f"{BASE}/{slug}/file", params={**WS, "path": "index.html"}),
            await http.post(f"{BASE}/", json={**WS, "title": "x"}),
            await http.post(f"{BASE}/{slug}/preview-token", json=WS),
            await http.put(f"{BASE}/{slug}/file", json={**WS, "path": "a", "content": "b"}),
        ):
            assert response.status_code == 403


@pytest.mark.asyncio
async def test_a_project_is_reached_through_its_own_workspace_only(world) -> None:
    slug = await _create(world)
    other = {"workspace_id": "ws-2"}
    async with world.as_("owner") as http:
        assert (await http.get(f"{BASE}/{slug}", params=other)).status_code == 403
        assert (await http.post(f"{BASE}/{slug}/save", json=other)).status_code == 403
        assert (await http.post(f"{BASE}/", json={**other, "title": "x"})).status_code == 403


@pytest.mark.asyncio
async def test_the_apps_section_must_be_on_for_the_role(tmp_path: Path) -> None:
    nexus = NexusIam(
        FeatureFlagsConfig(enabled_features=["apps", "chat"], role_baseline={"owner": ["apps"]})
    )
    nexus.grant("member", "member", nexus.workspace("org-1", "ws-1"))
    app = FastAPI()
    app.include_router(adapter.router, prefix=BASE)
    app.dependency_overrides[get_current_user_required] = lambda: SimpleNamespace(id="member")
    with nexus.installed():
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://t") as http:
            denied = await http.get(f"{BASE}/", params=WS)
    assert denied.status_code == 403
    assert "not available" in denied.json()["detail"]


@pytest.mark.asyncio
async def test_creating_a_project_places_its_drafts_in_the_workspace(world) -> None:
    key = encode_id(["nexus", "app-projects", "ws-1", "x", "files", "a.css"], "path")
    assert world.nexus.iam.resolve_placement("object_storage", key) == PLATFORM
    await _create(world)
    assert world.nexus.iam.resolve_placement("object_storage", key) == workspace_container(
        "org-1", "ws-1"
    )
    assert draft_placement("ws-1").id_key() == "nexus/app-projects/ws-1/*"


def test_the_shared_repository_is_worked_in_as_nexus_for_no_user() -> None:
    seen: list[tuple[str, str | None]] = []

    class Spy:
        def list_branches(self, repo_id):
            context = current_call_context()
            seen.append((context.principal.id, context.on_behalf_of and context.on_behalf_of.id))
            return []

    repository = AppProjectRepositoryGit(Spy(), "abi/monorepo")  # type: ignore[arg-type]
    assert repository.list_projects("ws-1") == []
    assert seen == [("api", None)]
