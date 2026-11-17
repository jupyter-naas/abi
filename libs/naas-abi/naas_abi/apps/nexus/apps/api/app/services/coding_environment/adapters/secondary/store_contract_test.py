"""``CodingEnvironmentStorePort``: one contract, run on every adapter (the SQL
store on a SQLite Nexus database, and the memory store)."""

from __future__ import annotations

from collections.abc import AsyncIterator, Awaitable, Callable
from dataclasses import dataclass
from datetime import datetime

import pytest
import pytest_asyncio
from naas_abi.apps.nexus.apps.api.app.models import WorkspaceModel
from naas_abi.apps.nexus.apps.api.app.services.coding_environment.adapters.secondary.memory import (
    MemoryCodingEnvironmentStore,
)
from naas_abi.apps.nexus.apps.api.app.services.coding_environment.adapters.secondary.sql import (
    SqlCodingEnvironmentStore,
)
from naas_abi.apps.nexus.apps.api.app.services.coding_environment.port import (
    CodingEnvironmentRecord,
    CodingEnvironmentStorePort,
    CodingWorkspace,
    EnvironmentAlreadyRecorded,
)


@dataclass
class World:
    store: CodingEnvironmentStorePort
    # Adds a workspace the way its adapter stores one.
    workspace: Callable[[CodingWorkspace], Awaitable[None]]


@pytest_asyncio.fixture(params=["sql", "memory"])
async def world(request: pytest.FixtureRequest, nexus_db) -> AsyncIterator[World]:
    if request.param == "memory":
        memory = MemoryCodingEnvironmentStore()

        async def add_memory(workspace: CodingWorkspace) -> None:
            memory.workspaces[workspace.id] = workspace

        yield World(memory, add_memory)
        return

    async with nexus_db() as db:

        async def add_row(workspace: CodingWorkspace) -> None:
            db.add(
                WorkspaceModel(
                    id=workspace.id,
                    name=workspace.id,
                    slug=workspace.id,
                    owner_id="owner",
                    organization_id=workspace.organization_id,
                    coding_default_repo_id=workspace.coding_default_repo_id,
                )
            )
            await db.commit()

        yield World(SqlCodingEnvironmentStore(db), add_row)


def _env(env_id: str, **fields: str | None) -> CodingEnvironmentRecord:
    values: dict = {"workspace_id": "ws-1", "user_id": "u1", **fields}
    return CodingEnvironmentRecord(id=env_id, **values)


@pytest.mark.asyncio
async def test_a_workspace_is_read_and_its_default_repo_set(world: World) -> None:
    store = world.store
    await world.workspace(CodingWorkspace(id="ws-1", organization_id="org-1"))
    await world.workspace(CodingWorkspace(id="ws-2", coding_default_repo_id="abi/two"))

    assert await store.get_workspace("ws-1") == CodingWorkspace(id="ws-1", organization_id="org-1")
    assert await store.get_workspace("nope") is None
    assert await store.set_default_repo("ws-1", "abi/one") is True
    assert await store.set_default_repo("nope", "abi/one") is False
    assert (await store.get_workspace("ws-1")).coding_default_repo_id == "abi/one"  # type: ignore[union-attr]
    assert sorted(await store.default_repos()) == [("ws-1", "abi/one"), ("ws-2", "abi/two")]


@pytest.mark.asyncio
async def test_an_environment_is_added_read_and_deleted(world: World) -> None:
    store = world.store
    await store.add(_env("env-1", repo_id="abi/lib", sidecar_base="http://a", sidecar_secret="s"))

    found = await store.get("env-1")
    assert found is not None
    assert (found.workspace_id, found.user_id, found.repo_id) == ("ws-1", "u1", "abi/lib")
    assert (found.sidecar_base, found.sidecar_secret) == ("http://a", "s")
    assert isinstance(found.created_at, datetime)
    assert [e.id for e in await store.list_all()] == ["env-1"]

    with pytest.raises(EnvironmentAlreadyRecorded):
        await store.add(_env("env-1"))
    assert (await store.get("env-1")).repo_id == "abi/lib"  # type: ignore[union-attr]

    await store.delete("env-1")
    await store.delete("env-1")
    assert await store.get("env-1") is None
    assert await store.list_all() == []


@pytest.mark.asyncio
async def test_repos_are_mapped_for_the_workspace_s_environments_only(world: World) -> None:
    store = world.store
    await store.add(_env("env-1", repo_id="abi/lib"))
    await store.add(_env("env-2"))
    await store.add(_env("env-3", workspace_id="ws-2", repo_id="abi/other"))

    assert await store.repos_by_environment("ws-1", ["env-1", "env-2", "env-3", "env-x"]) == {
        "env-1": "abi/lib",
        "env-2": None,
    }
    assert await store.repos_by_environment("ws-1", []) == {}


@pytest.mark.asyncio
async def test_bindings_are_found_by_label_for_the_user_and_workspace(world: World) -> None:
    store = world.store
    await store.add(_env("env-1", label="slides/ws-1/deck"))
    await store.add(_env("env-2", label="slides/deck"))
    await store.add(_env("env-3", label="slides/ws-1/deck", user_id="u2"))
    await store.add(_env("env-4", label="slides/ws-1/deck", workspace_id="ws-2"))
    await store.add(_env("env-5", label="documents/ws-1/deck"))

    found = await store.find_by_labels(
        workspace_id="ws-1", user_id="u1", labels=["slides/ws-1/deck", "slides/deck"]
    )
    assert sorted(e.id for e in found) == ["env-1", "env-2"]
    assert await store.find_by_labels(workspace_id="ws-1", user_id="u1", labels=[]) == []


@pytest.mark.asyncio
async def test_bind_replaces_the_label_s_other_bindings_and_keeps_a_readopted_one(
    world: World,
) -> None:
    store = world.store
    await store.add(_env("old", label="docs/ws-1/a", sidecar_base="http://old"))
    await store.add(_env("other-user", label="docs/ws-1/a", user_id="u2"))
    await store.add(_env("other-label", label="docs/ws-1/b"))

    await store.bind(_env("new", label="docs/ws-1/a", sidecar_base="http://1", sidecar_secret="s1"))
    first = await store.get("new")
    assert first is not None and first.created_at is not None
    assert await store.get("old") is None
    assert await store.get("other-user") is not None
    assert await store.get("other-label") is not None

    # The same environment adopted again: updated in place, its creation kept.
    await store.bind(_env("new", label="docs/ws-1/a", sidecar_base="http://2", sidecar_secret="s2"))
    again = await store.get("new")
    assert again is not None
    assert (again.sidecar_base, again.sidecar_secret) == ("http://2", "s2")
    assert again.created_at == first.created_at
    assert sorted(e.id for e in await store.list_all()) == ["new", "other-label", "other-user"]


@pytest.mark.asyncio
async def test_the_sidecar_is_updated_in_place(world: World) -> None:
    store = world.store
    await store.add(_env("env-1", label="x", repo_id="abi/lib", sidecar_base="http://a"))

    await store.update_sidecar("env-1", sidecar_base="http://b", sidecar_secret="s")
    await store.update_sidecar("missing", sidecar_base="http://b", sidecar_secret="s")

    found = await store.get("env-1")
    assert found is not None
    assert (found.sidecar_base, found.sidecar_secret, found.repo_id) == ("http://b", "s", "abi/lib")
    assert await store.get("missing") is None
