"""The model catalog is the platform's: workspace roles read it, only a platform admin edits it."""

from __future__ import annotations

from types import SimpleNamespace

import pytest
from fastapi import FastAPI
from httpx import ASGITransport, AsyncClient
from naas_abi.apps.nexus.apps.api.app.services.auth.adapters.primary.auth__primary_adapter__dependencies import (  # noqa: E501
    get_current_user_required,
)
from naas_abi.apps.nexus.apps.api.app.services.providers.adapters.primary import (
    providers__primary_adapter__FastAPI as adapter,
)
from naas_abi.apps.nexus.apps.api.app.services.providers.service import ProviderService


class _NoStore(ProviderService):
    """The catalog without a database: a platform admin's edit finds no model."""

    async def update_model(self, canonical_or_model_id, updates):
        return None


@pytest.fixture
def client(team):
    team.platform_admin("root")
    app = FastAPI()
    app.include_router(adapter.router, prefix="/api/providers")
    app.dependency_overrides[adapter.get_provider_service] = lambda: _NoStore()
    user = {"id": "viewer"}
    app.dependency_overrides[get_current_user_required] = lambda: SimpleNamespace(**user)

    def as_(user_id: str) -> AsyncClient:
        user["id"] = user_id
        return AsyncClient(transport=ASGITransport(app=app), base_url="http://t/api/providers")

    return as_


@pytest.mark.asyncio
async def test_every_workspace_role_reads_the_catalog_and_a_stranger_does_not(client) -> None:
    for role in ("viewer", "member", "admin", "owner", "root"):
        async with client(role) as http:
            assert (await http.get("/available")).status_code == 200, role
            models = await http.get("/models")
            assert models.status_code == 200, role
    async with client("viewer") as http:
        model_id = (await http.get("/models")).json()[0]["canonical_id"]
        assert (await http.get(f"/models/{model_id}")).status_code == 200
    async with client("stranger") as http:
        assert (await http.get("/available")).status_code == 403
        assert (await http.get("/models")).status_code == 403
        assert (await http.get(f"/models/{model_id}")).status_code == 403


@pytest.mark.asyncio
async def test_only_a_platform_admin_edits_a_model(client) -> None:
    async with client("viewer") as http:
        model_id = (await http.get("/models")).json()[0]["canonical_id"]
    for role in ("viewer", "member", "admin", "owner", "stranger"):
        async with client(role) as http:
            refused = await http.patch(f"/models/{model_id}", json={"description": "x"})
            assert refused.status_code == 403, role
    async with client("root") as http:
        assert (
            await http.patch("/models/no-such-model", json={"description": "x"})
        ).status_code == 404
