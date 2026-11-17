"""``GraphViewStorePort`` against every adapter, and ``ViewService``'s view and
folder rules on top of it."""

from __future__ import annotations

from collections.abc import AsyncIterator
from types import SimpleNamespace
from unittest.mock import patch

import pytest
import pytest_asyncio
from naas_abi import ABIModule
from naas_abi.apps.nexus.apps.api.app.models import UserModel, WorkspaceModel

# The view service imports the graph service, which reads the ontology base URI
# when it is imported (as in ``api/endpoints/view_test.py``).
_CONFIG = SimpleNamespace(
    configuration=SimpleNamespace(
        nexus_config=SimpleNamespace(ontology_base_uri="http://ontology.naas.ai/nexus/")
    )
)
with patch.object(ABIModule, "get_instance", return_value=_CONFIG):
    from naas_abi.apps.nexus.apps.api.app.services.view.adapters.secondary.memory import (
        MemoryGraphViewStore,
    )
    from naas_abi.apps.nexus.apps.api.app.services.view.adapters.secondary.sql import (
        SqlGraphViewStore,
    )
    from naas_abi.apps.nexus.apps.api.app.services.view.port import (
        GraphViewRecord,
        GraphViewStorePort,
    )
    from naas_abi.apps.nexus.apps.api.app.services.view.service import (
        ViewNotFoundError,
        ViewService,
    )


@pytest_asyncio.fixture(params=["sql", "memory"])
async def store(request: pytest.FixtureRequest, nexus_db) -> AsyncIterator[GraphViewStorePort]:
    if request.param == "memory":
        yield MemoryGraphViewStore()
        return
    async with nexus_db() as db:
        db.add(UserModel(id="u1", email="u1@example.com", name="U1"))
        db.add(UserModel(id="u2", email="u2@example.com", name="U2"))
        for ws in ("ws-1", "ws-2"):
            db.add(WorkspaceModel(id=ws, name=ws, slug=ws, owner_id="u1"))
        await db.commit()
    async with nexus_db() as db:
        yield SqlGraphViewStore(db)


def _view(view_id: str, workspace_id: str = "ws-1", **fields) -> GraphViewRecord:
    return GraphViewRecord(
        id=view_id,
        workspace_id=workspace_id,
        name=fields.pop("name", view_id),
        graph_id="g",
        graph_uri="urn:g",
        creator_id=fields.pop("creator_id", "u1"),
        state=fields.pop("state", {"selectedClassIds": ["urn:Person"]}),
        **fields,
    )


# -- the port ---------------------------------------------------------------------


@pytest.mark.asyncio
async def test_add_sets_the_timestamps_and_get_reads_it_back(store) -> None:
    added = await store.add(_view("v1", path="a/b", description="d"))

    assert added.created_at is not None and added.updated_at is not None
    got = await store.get("ws-1", "v1")
    assert got is not None
    assert (got.name, got.path, got.description, got.state) == (
        "v1",
        "a/b",
        "d",
        {"selectedClassIds": ["urn:Person"]},
    )


@pytest.mark.asyncio
async def test_a_view_belongs_to_its_workspace_only(store) -> None:
    await store.add(_view("v1"))
    await store.add(_view("v2", workspace_id="ws-2"))

    assert [v.id for v in await store.list("ws-1")] == ["v1"]
    assert await store.get("ws-2", "v1") is None
    assert await store.delete("ws-2", "v1") is False
    assert await store.save(_view("v1", workspace_id="ws-2")) is None


@pytest.mark.asyncio
async def test_save_replaces_the_fields_and_keeps_created_at(store) -> None:
    added = await store.add(_view("v1"))

    saved = await store.save(_view("v1", name="People", state={"spec": {"q": 1}}, kind="query"))

    assert saved is not None
    assert (saved.name, saved.kind, saved.state) == ("People", "query", {"spec": {"q": 1}})
    assert saved.created_at == added.created_at


@pytest.mark.asyncio
async def test_delete_removes_the_view(store) -> None:
    await store.add(_view("v1"))

    assert await store.delete("ws-1", "v1") is True
    assert await store.get("ws-1", "v1") is None


@pytest.mark.asyncio
async def test_move_sets_paths_of_the_named_views_only(store) -> None:
    await store.add(_view("v1", path="a"))
    await store.add(_view("v2", path="a/b"))
    await store.add(_view("v3", path="c"))

    await store.move("ws-1", {"v1": "x", "v2": "x/b", "v404": "nowhere"})

    paths = {v.id: v.path for v in await store.list("ws-1")}
    assert paths == {"v1": "x", "v2": "x/b", "v3": "c"}


# -- the service on the port ------------------------------------------------------


@pytest.mark.asyncio
async def test_lists_workspace_views_and_the_users_own(store) -> None:
    await store.add(_view("shared", creator_id="u2"))
    await store.add(_view("mine", visibility="private", creator_id="u1"))
    await store.add(_view("theirs", visibility="private", creator_id="u2"))
    service = ViewService(store=store)

    assert {v["id"] for v in await service.list_views("ws-1", user_id="u1")} == {"shared", "mine"}
    assert [v["id"] for v in await service.list_views("ws-1")] == ["shared"]


@pytest.mark.asyncio
async def test_lists_a_folder_alone_or_with_its_subtree(store) -> None:
    for view_id, path in (("root", ""), ("a", "a"), ("ab", "a/b"), ("ax", "ax")):
        await store.add(_view(view_id, path=path))
    service = ViewService(store=store)

    async def ids(path: str, recursive: bool) -> set[str]:
        views = await service.list_views("ws-1", user_id="u1", path=path, recursive=recursive)
        return {v["id"] for v in views}

    assert await ids("a", False) == {"a"}
    assert await ids("a", True) == {"a", "ab"}
    assert await ids("", True) == {"root", "a", "ab", "ax"}


@pytest.mark.asyncio
async def test_folders_count_their_views_and_subtree(store) -> None:
    for view_id, path in (("v1", "a"), ("v2", "a/b"), ("v3", "a/b")):
        await store.add(_view(view_id, path=path))

    folders = await ViewService(store=store).list_folders("ws-1", user_id="u1")

    assert folders == [
        {"path": "a", "name": "a", "view_count": 1, "total_count": 3},
        {"path": "a/b", "name": "b", "view_count": 2, "total_count": 2},
    ]


@pytest.mark.asyncio
async def test_renaming_a_folder_moves_its_subtree(store) -> None:
    for view_id, path in (("v1", "a"), ("v2", "a/b"), ("v3", "ab")):
        await store.add(_view(view_id, path=path))

    result = await ViewService(store=store).rename_folder(
        workspace_id="ws-1", from_path="a", to_path="z"
    )

    assert result["updated_count"] == 2
    assert {v.id: v.path for v in await store.list("ws-1")} == {"v1": "z", "v2": "z/b", "v3": "ab"}


@pytest.mark.asyncio
async def test_renaming_onto_a_same_named_view_needs_merge(store) -> None:
    await store.add(_view("v1", name="People", path="a"))
    await store.add(_view("v2", name="People", path="z"))
    service = ViewService(store=store)

    with pytest.raises(ValueError, match="merge=true"):
        await service.rename_folder(workspace_id="ws-1", from_path="a", to_path="z")

    merged = await service.rename_folder(
        workspace_id="ws-1", from_path="a", to_path="z", merge=True
    )
    assert merged["updated_count"] == 1


@pytest.mark.asyncio
async def test_create_update_delete_through_the_service(store) -> None:
    service = ViewService(store=store)
    created = await service.create_view(
        workspace_id="ws-1",
        name=" People ",
        view_type="network",
        kind="network",
        visibility="workspace",
        graph_id="g",
        graph_uri="urn:g",
        state={"selectedClassIds": ["urn:Person"]},
        creator="u1",
        path="/a//b/",
    )
    view_id = created["view_id"]

    updated = await service.update_view(view_id, workspace_id="ws-1", description="  ")
    assert updated["label"] == "People" and updated["description"] is None
    assert (await service.get_view(view_id, "ws-1"))["path"] == "a/b"

    await service.delete_view(f"/api/view/{view_id}", workspace_id="ws-1")
    with pytest.raises(ViewNotFoundError):
        await service.get_view(view_id, "ws-1")
