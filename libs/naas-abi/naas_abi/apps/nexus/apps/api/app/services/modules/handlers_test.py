"""The marketplace of modules: open to the roles that hold the marketplace feature."""

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
from naas_abi.apps.nexus.apps.api.app.services.modules import handlers
from naas_abi.apps.nexus.apps.api.app.services.modules.schema import ModulesResponse


def _app(user_id: str) -> FastAPI:
    app = FastAPI()
    app.include_router(handlers.router, prefix="/api/modules")
    app.dependency_overrides[get_current_user_required] = lambda: SimpleNamespace(id=user_id)
    return app


async def _get(user_id: str, path: str) -> int:
    transport = ASGITransport(app=_app(user_id))
    async with AsyncClient(transport=transport, base_url="http://t") as http:
        return (await http.get(path)).status_code


@pytest.fixture(autouse=True)
def modules(monkeypatch):
    async def listing():
        return ModulesResponse(installed=[], available=[])

    monkeypatch.setattr(handlers.ModulesService, "list_modules", staticmethod(listing))


@pytest.mark.asyncio
async def test_the_marketplace_follows_the_feature_of_the_role(team) -> None:
    # By default admins and owners hold "marketplace"; members and viewers do not.
    for path in ("/api/modules/?workspace_id=ws-1", "/api/modules/config?workspace_id=ws-1"):
        assert await _get("admin", path) == 200
        assert await _get("owner", path) == 200
        assert await _get("member", path) == 403
        assert await _get("viewer", path) == 403
        assert await _get("stranger", path) == 403


@pytest.mark.asyncio
async def test_viewers_read_the_marketplace_where_their_role_holds_it() -> None:
    flags = FeatureFlagsConfig(
        enabled_features=["marketplace", "chat"],
        role_baseline={
            "viewer": ["marketplace"],
            "member": ["marketplace"],
            "owner": ["marketplace"],
        },
    )
    nexus = NexusIam(flags)
    scope = nexus.workspace("org-1", "ws-1")
    nexus.grant("viewer", "viewer", scope)
    nexus.user("stranger")
    with nexus.installed():
        assert await _get("viewer", "/api/modules/?workspace_id=ws-1") == 200
        assert await _get("viewer", "/api/modules/config?workspace_id=ws-1") == 200
        assert await _get("stranger", "/api/modules/?workspace_id=ws-1") == 403
