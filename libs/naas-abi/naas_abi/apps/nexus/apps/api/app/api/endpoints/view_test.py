"""Graph views are workspace records (``view/<id>``): who lists, reads, writes them."""

from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import patch

import pytest
import pytest_asyncio
from fastapi import FastAPI
from naas_abi import ABIModule
from naas_abi.apps.nexus.apps.api.app.core.database import get_db
from naas_abi.apps.nexus.apps.api.app.models import GraphViewModel
from naas_abi.apps.nexus.apps.api.app.services.graph.testing import (
    acting_as_header,
    client,
    knowledge_team,
)
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

_CONFIG = SimpleNamespace(
    configuration=SimpleNamespace(
        nexus_config=SimpleNamespace(ontology_base_uri="http://ontology.naas.ai/nexus/")
    )
)
with patch.object(ABIModule, "get_instance", return_value=_CONFIG):
    from naas_abi.apps.nexus.apps.api.app.api.endpoints import view

BODY = {
    "workspace_id": "ws-1",
    "name": "People",
    "graph_id": "g",
    "graph_uri": "urn:g",
    "state": {"selectedClassIds": ["urn:Person"]},
}


@pytest_asyncio.fixture
async def app():
    engine = create_async_engine("sqlite+aiosqlite://")
    async with engine.begin() as connection:
        await connection.run_sync(GraphViewModel.__table__.create)
    sessions = async_sessionmaker(engine, expire_on_commit=False)

    async def db():
        async with sessions() as session:
            yield session

    application = FastAPI()
    application.include_router(view.router, prefix="/api/view")
    application.dependency_overrides[get_db] = db
    acting_as_header(application)
    # The graph service is only reached once the caller was let into the section.
    from naas_abi.apps.nexus.apps.api.app.services.registry import ServiceRegistry

    with (
        knowledge_team(),
        patch.object(ServiceRegistry, "instance", return_value=SimpleNamespace(graph=None)),
    ):
        yield application
    await engine.dispose()


async def create(application: FastAPI, user: str = "member", workspace: str = "ws-1") -> str:
    async with client(application, user) as http:
        response = await http.post("/api/view", json={**BODY, "workspace_id": workspace})
        assert response.status_code == 200, response.text
        return response.json()["view_id"]


@pytest.mark.asyncio
async def test_viewers_read_views_and_change_nothing(app) -> None:
    view_id = await create(app)
    async with client(app, "viewer") as viewer:
        listed = await viewer.get("/api/view/list", params={"workspace_id": "ws-1"})
        assert [v["id"] for v in listed.json()] == [view_id]
        assert (
            await viewer.get("/api/view/folders", params={"workspace_id": "ws-1"})
        ).status_code == 200
        got = await viewer.get(f"/api/view/{view_id}", params={"workspace_id": "ws-1"})
        assert got.status_code == 200
        assert (await viewer.post("/api/view", json=BODY)).status_code == 403
        assert (
            await viewer.put(f"/api/view/{view_id}", json={"workspace_id": "ws-1", "name": "x"})
        ).status_code == 403
        assert (
            await viewer.patch(f"/api/view/{view_id}", json={"workspace_id": "ws-1", "name": "x"})
        ).status_code == 403
        assert (
            await viewer.delete(f"/api/view/{view_id}", params={"workspace_id": "ws-1"})
        ).status_code == 403
        rename = {"workspace_id": "ws-1", "from_path": "a", "to_path": "b"}
        assert (await viewer.put("/api/view/folders/rename", json=rename)).status_code == 403
        assert (await viewer.get(f"/api/view/{view_id}")).status_code == 422


@pytest.mark.asyncio
async def test_members_create_update_rename_and_delete_views(app) -> None:
    view_id = await create(app)
    async with client(app, "member") as member:
        updated = await member.put(
            f"/api/view/{view_id}", json={"workspace_id": "ws-1", "name": "Renamed"}
        )
        assert updated.status_code == 200 and updated.json()["name"] == "Renamed"
        rename = {"workspace_id": "ws-1", "from_path": "a", "to_path": "b"}
        assert (await member.put("/api/view/folders/rename", json=rename)).status_code != 403
        deleted = await member.delete(f"/api/view/{view_id}", params={"workspace_id": "ws-1"})
        assert deleted.status_code == 200


@pytest.mark.asyncio
async def test_a_view_of_another_workspace_is_reached_by_nobody_outside_it(app) -> None:
    """A view could be read by naming its id and workspace, signed in as anyone."""
    view_id = await create(app)
    for user in ("stranger", "member2", "admin2", "owner2"):
        async with client(app, user) as other:
            params = {"workspace_id": "ws-1"}
            assert (await other.get(f"/api/view/{view_id}", params=params)).status_code == 403, user
            assert (await other.get("/api/view/list", params=params)).status_code == 403, user
            assert (
                await other.get(f"/api/view/{view_id}/overview", params=params)
            ).status_code == 403
            assert (
                await other.get(f"/api/view/{view_id}/network", params=params)
            ).status_code == 403
            assert (await other.post("/api/view", json=BODY)).status_code == 403
            assert (await other.delete(f"/api/view/{view_id}", params=params)).status_code == 403
            filters = await other.get("/api/view/filters/options", params=params)
            assert filters.status_code == 403
            preview = {"workspace_id": "ws-1"}
            assert (await other.post("/api/view/filters/preview", json=preview)).status_code == 403
