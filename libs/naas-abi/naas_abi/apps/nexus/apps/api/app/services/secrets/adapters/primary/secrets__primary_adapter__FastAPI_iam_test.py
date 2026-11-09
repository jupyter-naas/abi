"""Workspace secrets: viewers and members list them masked, admins change them."""

from __future__ import annotations

from types import SimpleNamespace

import pytest
from fastapi import FastAPI
from httpx import ASGITransport, AsyncClient
from naas_abi.apps.nexus.apps.api.app.core.config import FeatureFlagsConfig
from naas_abi.apps.nexus.apps.api.app.services.auth.adapters.primary.auth__primary_adapter__dependencies import (  # noqa: E501
    get_current_user_required,
)
from naas_abi.apps.nexus.apps.api.app.services.iam.testing import NexusIam
from naas_abi.apps.nexus.apps.api.app.services.secrets.adapters.primary import (
    secrets__primary_adapter__FastAPI as adapter,
)
from naas_abi.apps.nexus.apps.api.app.services.secrets.port import SecretRecord
from naas_abi.apps.nexus.apps.api.app.services.secrets.service import SecretsService


class MemorySecrets:
    """The persistence port, in memory."""

    def __init__(self, *records: SecretRecord) -> None:
        self.rows = {r.id: r for r in records}

    async def list_all(self):
        return list(self.rows.values())

    async def list_by_workspace(self, workspace_id):
        return [r for r in self.rows.values() if r.workspace_id == workspace_id]

    async def get_by_workspace_key(self, workspace_id, key):
        return next((r for r in await self.list_by_workspace(workspace_id) if r.key == key), None)

    async def get_by_id(self, secret_id):
        return self.rows.get(secret_id)

    async def create(self, record):
        self.rows[record.id] = record
        return record

    async def save(self, record):
        self.rows[record.id] = record

    async def delete(self, secret_id):
        return self.rows.pop(secret_id, None) is not None

    async def commit(self):
        return None


def _secret(secret_id: str, workspace: str, key: str, value: str = "sk-123456789") -> SecretRecord:
    return SecretRecord(
        id=secret_id,
        workspace_id=workspace,
        key=key,
        encrypted_value=SecretsService.encrypt(value),
        description="",
        category="api_keys",
    )


@pytest.fixture
def world():
    # Every role holds the settings section, so only the action's level decides.
    everything = ["settings", "chat"]
    flags = FeatureFlagsConfig(
        enabled_features=everything,
        role_baseline=dict.fromkeys(("owner", "admin", "member", "viewer"), everything),
    )
    nexus = NexusIam(flags)
    scope = nexus.workspace("org-1", "ws-1")
    nexus.workspace("org-1", "ws-2")
    for user in ("owner", "admin", "member", "viewer"):
        nexus.grant(user, user, scope)
    nexus.user("stranger")
    store = MemorySecrets(_secret("s1", "ws-1", "OPENAI_API_KEY"), _secret("s2", "ws-2", "OTHER"))
    app = FastAPI()
    app.include_router(adapter.router, prefix="/api/secrets")
    app.dependency_overrides[adapter.get_secrets_service] = lambda: SecretsService(adapter=store)
    user = {"id": "member"}
    app.dependency_overrides[get_current_user_required] = lambda: SimpleNamespace(**user)

    def as_(user_id: str) -> AsyncClient:
        user["id"] = user_id
        return AsyncClient(transport=ASGITransport(app=app), base_url="http://t")

    with nexus.installed():
        yield SimpleNamespace(as_=as_, store=store)


NEW = {"workspace_id": "ws-1", "key": "NEW_KEY", "value": "a-long-secret-value"}
IMPORT = {"workspace_id": "ws-1", "env_content": "A=1\nB=2"}


@pytest.mark.asyncio
async def test_roles_below_admin_list_masked_values_only(world) -> None:
    for role in ("viewer", "member", "admin", "owner"):
        async with world.as_(role) as http:
            response = await http.get("/api/secrets/ws-1")
            assert response.status_code == 200, role
            (row,) = response.json()
            assert row["masked_value"] == "sk-1****6789"
            assert "sk-123456789" not in response.text


@pytest.mark.asyncio
async def test_only_admins_and_owners_change_secrets(world) -> None:
    for role in ("viewer", "member"):
        async with world.as_(role) as http:
            posted = await http.post("/api/secrets", json=NEW)
            assert posted.status_code == 403, role
            assert posted.json()["detail"] == "Only admins and owners can manage secrets"
            assert (
                await http.put("/api/secrets/s1", json={"value": "changed-value"})
            ).status_code == 403
            assert (await http.delete("/api/secrets/s1")).status_code == 403
            assert (await http.post("/api/secrets/import", json=IMPORT)).status_code == 403
    assert set(world.store.rows) == {"s1", "s2"}
    for role in ("admin", "owner"):
        async with world.as_(role) as http:
            assert (
                await http.post("/api/secrets", json={**NEW, "key": f"K_{role}"})
            ).status_code == 200
            assert (
                await http.put("/api/secrets/s1", json={"description": role})
            ).status_code == 200
            assert (await http.post("/api/secrets/import", json=IMPORT)).json() == {
                "imported": 2 if role == "admin" else 0,
                "updated": 0 if role == "admin" else 2,
            }
    async with world.as_("admin") as http:
        assert (await http.delete("/api/secrets/s1")).json() == {"status": "deleted"}


@pytest.mark.asyncio
async def test_a_stranger_and_another_workspace_get_nothing(world) -> None:
    async with world.as_("stranger") as http:
        assert (await http.get("/api/secrets/ws-1")).status_code == 403
        assert (await http.post("/api/secrets", json=NEW)).status_code == 403
        assert (await http.put("/api/secrets/s1", json={"value": "x"})).status_code == 403
    async with world.as_("owner") as http:
        # The owner of ws-1 holds nothing in ws-2, whatever the secret's id.
        assert (await http.get("/api/secrets/ws-2")).status_code == 403
        assert (await http.put("/api/secrets/s2", json={"value": "changed"})).status_code == 403
        assert (await http.delete("/api/secrets/s2")).status_code == 403
        assert (
            await http.post("/api/secrets", json={**NEW, "workspace_id": "ws-2"})
        ).status_code == 403
        assert (await http.put("/api/secrets/missing", json={"value": "x"})).status_code == 404
    assert "s2" in world.store.rows


@pytest.mark.asyncio
async def test_the_settings_section_must_be_on_for_the_role() -> None:
    flags = FeatureFlagsConfig(
        enabled_features=["settings", "chat"],
        role_baseline={"owner": ["settings", "chat"], "admin": ["chat"]},
    )
    nexus = NexusIam(flags)
    scope = nexus.workspace("org-1", "ws-1")
    nexus.grant("admin", "admin", scope)
    app = FastAPI()
    app.include_router(adapter.router, prefix="/api/secrets")
    app.dependency_overrides[adapter.get_secrets_service] = lambda: SecretsService(
        adapter=MemorySecrets()
    )
    app.dependency_overrides[get_current_user_required] = lambda: SimpleNamespace(id="admin")
    with nexus.installed():
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://t") as http:
            assert (await http.get("/api/secrets/ws-1")).status_code == 403
            assert (await http.post("/api/secrets", json=NEW)).status_code == 403


@pytest.mark.asyncio
async def test_the_runtime_resolves_a_secret_without_a_user(world) -> None:
    service = SecretsService(adapter=world.store)
    assert await service.resolve_runtime_secret("ws-1", "OPENAI_API_KEY") == "sk-123456789"
    assert await service.resolve_runtime_secret("ws-2", "OPENAI_API_KEY") is None
