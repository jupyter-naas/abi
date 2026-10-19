"""A new workspace places its own resources, not everything that exists."""

from __future__ import annotations

import pytest
from naas_abi.apps.nexus.apps.api.app.services.iam import placements
from naas_abi.apps.nexus.apps.api.app.services.iam.placements import Placement
from naas_abi_core.engine.call_context import as_service_account
from naas_abi_core.services.iam.names import encode_id


@pytest.fixture
def registered(monkeypatch):
    monkeypatch.setattr(placements, "SOURCES", [])
    monkeypatch.setattr(placements, "WORKSPACE_HOOKS", [])


@pytest.mark.asyncio
async def test_a_new_workspace_runs_its_hooks_and_never_the_sources(nexus_iam, registered) -> None:
    nexus_iam.workspace("org-1", "ws-1")
    nexus_iam.workspace("org-1", "ws-2")
    scanned: list[str] = []
    hooked: list[str] = []

    @placements.placement_source
    async def everything(db) -> list[Placement]:
        scanned.append("scan")
        return [Placement("object_storage", ("workspaces", "ws-1"), "ws-1", prefix=True)]

    @placements.on_workspace_created
    async def just_this_one(db, workspace_id: str) -> list[Placement]:
        hooked.append(workspace_id)
        return [
            Placement("object_storage", ("workspaces", workspace_id), workspace_id, prefix=True)
        ]

    @placements.on_workspace_created
    async def broken(db, workspace_id: str) -> list[Placement]:
        raise RuntimeError("one domain's failure stops no other")

    written = await placements.place_new_workspace(None, "ws-2")  # type: ignore[arg-type]

    assert (hooked, scanned, written) == (["ws-2"], [], 1)
    with as_service_account("api"):
        found = {(p.id_key, p.workspace) for p in nexus_iam.iam.list_placements("object_storage")}
    assert found == {(f"{encode_id(('workspaces', 'ws-2'), 'path')}/*", "ws-2")}


@pytest.mark.asyncio
async def test_placing_again_writes_nothing(nexus_iam, registered) -> None:
    nexus_iam.workspace("org-1", "ws-1")

    @placements.on_workspace_created
    async def drive(db, workspace_id: str) -> list[Placement]:
        return [
            Placement("object_storage", ("workspaces", workspace_id), workspace_id, prefix=True)
        ]

    assert await placements.place_new_workspace(None, "ws-1") == 1  # type: ignore[arg-type]
    assert await placements.place_new_workspace(None, "ws-1") == 0  # type: ignore[arg-type]
