"""What is private to the person stays private in a view: their conversations, My Drive,
coding environments, workflow runs, the workspace's secrets and their personal API keys
answer empty (or "not found" for one item) in a view, and answer as usual outside one.

The real routes of the application over the test world of ``view_as_http_test``.
"""

from __future__ import annotations

from types import SimpleNamespace

import pytest
import pytest_asyncio
from naas_abi.apps.nexus.apps.api.app.core.feature_flags import KNOWN_FEATURE_KEYS
from naas_abi.apps.nexus.apps.api.app.services.coding_environment.adapters.primary import (
    coding_environment__primary_adapter__FastAPI as coding_api,
)
from naas_abi.apps.nexus.apps.api.app.services.files import placement
from naas_abi.apps.nexus.apps.api.app.services.view_as.full_app_testing import (
    bind_database,
    build_full_app,
    engine_iam_installed,
    services_installed,
)
from naas_abi.apps.nexus.apps.api.app.services.view_as.view_as_http_test import (  # noqa: F401
    ALPHA,
    BRAVO,
    start,
)
from naas_abi.apps.nexus.apps.api.app.services.workflows import factory as workflows_factory
from naas_abi.apps.nexus.apps.api.app.services.workflows.adapters.primary import (
    workflows__primary_adapter__FastAPI as workflows_api,
)
from naas_abi_core.services.object_storage.adapters.secondary.ObjectStorageSecondaryAdapterFS import (  # noqa: E501
    ObjectStorageSecondaryAdapterFS,
)
from naas_abi_core.services.object_storage.ObjectStorageService import ObjectStorageService


class FakeCoding:
    """The coding environment service: who it ensured, and one environment per owner."""

    def __init__(self) -> None:
        self.ensured: list[str] = []

    def ensure_user(self, *, external_id, email, username) -> str:
        self.ensured.append(external_id)
        return f"coder-{external_id}"

    def list_environments(self, *, user_id):
        return [SimpleNamespace(id="env-1", name="dave-env", phase="running", agent_ready=True)]

    def get_status(self, *, workspace_id):
        return SimpleNamespace(id=workspace_id, name="dave-env", phase="running", agent_ready=True)

    def get_workspace_ui_url(self, *, workspace_id):
        return None

    def get_logs(self, *, workspace_id):
        return ["secret line"]


class FakeWorkflows:
    def __init__(self) -> None:
        self.asked: list[str] = []

    async def own_runs(self, user_id, workspace_id):
        self.asked.append(user_id)
        return []

    async def own_run(self, user_id, workspace_id, module_id, run_id):
        self.asked.append(user_id)
        raise AssertionError("a view never asks for the person's runs")


@pytest_asyncio.fixture
async def full(world, tmp_path, monkeypatch):
    app = build_full_app()
    bind_database(monkeypatch)
    storage = ObjectStorageService(ObjectStorageSecondaryAdapterFS(str(tmp_path / "storage")))
    storage.put_object("naas_abi/my-drive/dave", "diary.md", b"# Dave's diary")
    storage.put_object("naas_abi/workspace-drive/alpha", "shared.md", b"# shared")
    app.state.object_storage = storage
    coding, workflows = FakeCoding(), FakeWorkflows()
    app.dependency_overrides[coding_api._get_coding_environment_service] = lambda: coding
    monkeypatch.setattr(workflows_factory, "_service", workflows)
    app.dependency_overrides[workflows_api.get_workflows_service] = lambda: workflows
    placement._PLACED.clear()
    world.app = app
    world.coding, world.workflows = coding, workflows
    everything = list(KNOWN_FEATURE_KEYS)
    world.nexus.flags.enabled_features = everything  # the deployment offers every feature
    for person in ("dave", "carol", "bob"):
        world.nexus.give_features(world.principals[person], everything, world.alpha)
    with services_installed(), engine_iam_installed(world.iam):
        yield world


async def _as_viewer_of(world, person: str):
    root = await world.sign_in("root")
    started = await start(root, world, person)
    assert started.status_code == 200, started.text
    return root


@pytest.mark.asyncio
async def test_a_persons_conversations_are_private_to_them(full) -> None:
    dave = await full.sign_in("dave")
    made = await dave.post("/api/chat/conversations", json={"workspace_id": ALPHA, "title": "Pay"})
    assert made.status_code == 200, made.text
    conversation = made.json()["id"]
    listing = f"/api/chat/conversations?workspace_id={ALPHA}"
    assert [c["id"] for c in (await dave.get(listing)).json()] == [conversation]
    assert (await dave.get(f"/api/chat/conversations/{conversation}")).status_code == 200

    root = await _as_viewer_of(full, "dave")

    assert (await root.get(listing)).json() == []
    for route in (
        f"/api/chat/conversations/{conversation}",
        f"/api/chat/conversations/{conversation}?include_messages=false",
        "/api/chat/ingestion-jobs/job-1",
    ):
        answered = await root.get(route)
        assert answered.status_code == 404, route
    # The conversation's export is a read sent by POST that a view refuses.
    exported = await root.post(
        f"/api/chat/conversations/{conversation}/export", json={"format": "markdown"}
    )
    assert exported.status_code == 403
    assert exported.json()["detail"] == "Read-only: you are viewing as Dave"
    # Ended, the person's own session still has all of it.
    await root.delete("/api/iam/view-as")
    assert [c["id"] for c in (await dave.get(listing)).json()] == [conversation]


@pytest.mark.asyncio
async def test_a_persons_my_drive_is_private_to_them(full) -> None:
    dave = await full.sign_in("dave")
    mine = f"/api/files/?workspace_id={ALPHA}&scope=my_drive"
    names = [f["name"] for f in (await dave.get(mine)).json()["files"]]
    assert "diary.md" in names

    root = await _as_viewer_of(full, "dave")

    listed = await root.get(mine)
    assert listed.status_code == 200 and listed.json()["files"] == []
    for suffix in ("diary.md", "raw/diary.md", "preview/pdf/diary.md", "archive/diary.md"):
        route = f"/api/files/{suffix}?workspace_id={ALPHA}&scope=my_drive"
        assert (await root.get(route)).status_code == 404, suffix
    # The workspace's own drive, shared with the person, is shown.
    shared = await root.get(f"/api/files/?workspace_id={ALPHA}")
    assert shared.status_code == 200
    assert "shared.md" in [f["name"] for f in shared.json()["files"]]


@pytest.mark.asyncio
async def test_a_persons_coding_environments_are_private_to_them(full) -> None:
    dave = await full.sign_in("dave")
    mine = await dave.get(f"/api/coding-environments?workspace_id={ALPHA}")
    assert mine.status_code == 200, mine.text
    assert [e["id"] for e in mine.json()] == ["env-1"]
    assert full.coding.ensured == ["dave"]
    full.coding.ensured.clear()

    root = await _as_viewer_of(full, "dave")

    assert (await root.get(f"/api/coding-environments?workspace_id={ALPHA}")).json() == []
    for tail in ("env-1", "env-1/logs", "env-1/access"):
        route = f"/api/coding-environments/{tail}?workspace_id={ALPHA}"
        assert (await root.get(route)).status_code == 404, tail
    assert full.coding.ensured == []  # no Coder user is made by a page load in a view


@pytest.mark.asyncio
async def test_a_persons_workflow_runs_are_private_to_them(full) -> None:
    dave = await full.sign_in("dave")
    base = f"/api/workspaces/{ALPHA}/workflows"
    assert (await dave.get(f"{base}/runs")).status_code == 200
    assert full.workflows.asked == ["dave"]
    full.workflows.asked.clear()

    root = await _as_viewer_of(full, "dave")

    assert (await root.get(f"{base}/runs")).json() == {"runs": []}
    assert (await root.get(f"{base}/some.module/runs/run-1")).status_code == 404
    assert full.workflows.asked == []


@pytest.mark.asyncio
async def test_the_workspaces_secrets_are_not_shown_in_a_view(full) -> None:
    carol = await full.sign_in("carol")
    made = await carol.post(
        "/api/secrets",
        json={"workspace_id": ALPHA, "key": "STRIPE_KEY", "value": "sk_live_123456"},
    )
    assert made.status_code == 200, made.text
    listed = await carol.get(f"/api/secrets/{ALPHA}")
    assert [s["key"] for s in listed.json()] == ["STRIPE_KEY"]

    root = await _as_viewer_of(full, "carol")

    seen = await root.get(f"/api/secrets/{ALPHA}")
    assert seen.status_code == 200 and seen.json() == []
    assert "sk_live" not in seen.text and "STRIPE_KEY" not in seen.text


@pytest.mark.asyncio
async def test_a_persons_personal_api_keys_are_private_to_them(full) -> None:
    dave = await full.sign_in("dave")
    made = await dave.post("/api/iam/api-keys", json={"name": "laptop"})
    assert made.status_code == 201, made.text
    assert [k["name"] for k in (await dave.get("/api/iam/api-keys")).json()] == ["laptop"]

    root = await _as_viewer_of(full, "dave")

    seen = await root.get("/api/iam/api-keys")
    assert seen.status_code == 200 and seen.json() == []
    # Nothing else of the keys is reachable: a key is made and revoked by a write.
    assert (await root.post("/api/iam/api-keys", json={"name": "x"})).status_code == 403
    assert (await root.get("/api/iam/token")).status_code in (403, 404, 405)
