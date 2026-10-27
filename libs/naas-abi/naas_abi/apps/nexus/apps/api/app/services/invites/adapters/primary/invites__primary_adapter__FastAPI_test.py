"""Invitations and IdP group bindings through the Nexus routes, on a real IAM: a
person who may invite still gives no role that grants more than they hold, and
the 403 says what they do not hold."""

from __future__ import annotations

import re
from datetime import datetime
from types import SimpleNamespace
from typing import Any

import pytest
import pytest_asyncio
from fastapi import FastAPI
from httpx import ASGITransport, AsyncClient
from naas_abi.apps.nexus.apps.api.app.core.database import get_db
from naas_abi.apps.nexus.apps.api.app.models import (
    OrganizationModel,
    UserModel,
    WorkspaceModel,
)
from naas_abi.apps.nexus.apps.api.app.services.auth.adapters.primary.auth__primary_adapter__dependencies import (  # noqa: E501
    get_current_user_required,
)
from naas_abi.apps.nexus.apps.api.app.services.exceptions import (
    register_service_exception_handlers,
)
from naas_abi.apps.nexus.apps.api.app.services.iam.names import workspace_scope
from naas_abi.apps.nexus.apps.api.app.services.invites import runtime as invites_runtime
from naas_abi.apps.nexus.apps.api.app.services.invites.adapters.primary.invites__primary_adapter__FastAPI import (  # noqa: E501
    idp_groups_router,
)
from naas_abi.apps.nexus.apps.api.app.services.invites.adapters.secondary.engine import (
    EngineGrantsGateway,
)
from naas_abi.apps.nexus.apps.api.app.services.invites.service import InvitationService
from naas_abi.apps.nexus.apps.api.app.services.invites.service_test import (
    BUILTIN,
    NOW,
    Directories,
    Mailer,
    Store,
)
from naas_abi.apps.nexus.apps.api.app.services.workspaces.adapters.primary import (
    workspaces__primary_adapter__FastAPI as workspaces_module,
)
from naas_abi_core.engine.call_context import as_service_account
from naas_abi_core.services.iam.IAMService import LEGACY_NEXUS_ISSUER

WS1 = workspace_scope("org-1", "ws-1")
REFUSAL = "You cannot grant what you do not hold"


def _inviter(team) -> None:
    """``inviter`` may invite to ws-1 and attach member and viewer there, and
    holds a viewer's reach: it lacks what member grants."""
    with as_service_account("engine"):
        inviter = team.iam.ensure_user(LEGACY_NEXUS_ISSUER, "inviter", provider="nexus")
        policy = team.iam.create_policy(
            "inviter",
            {
                "version": "2026-10-13",
                "statements": [
                    {
                        "effect": "Allow",
                        "actions": ["nexus:InviteWorkspaceMember"],
                        "resources": ["${scope}:nexus:member/*"],
                    },
                    {
                        "effect": "Allow",
                        "actions": ["iam:AttachPolicy"],
                        "resources": [
                            "${scope}:iam:attachment/builtin.member/*",
                            "${scope}:iam:attachment/builtin.viewer/*",
                        ],
                    },
                ],
            },
        )
        team.iam.attach_policy(policy.id, inviter.id, WS1)
        team.iam.attach_policy("builtin.viewer", inviter.id, WS1)


@pytest_asyncio.fixture
async def api(team, nexus_db, monkeypatch):
    now = datetime(2026, 1, 1)
    async with nexus_db() as db:
        for user in ("owner", "admin", "inviter"):
            db.add(
                UserModel(
                    id=user,
                    email=f"{user}@example.com",
                    name=user.title(),
                    created_at=now,
                    updated_at=now,
                )
            )
        db.add(OrganizationModel(id="org-1", name="Org", slug="org", owner_id="owner"))
        await db.flush()
        db.add(
            WorkspaceModel(
                id="ws-1",
                name="WS",
                slug="ws",
                owner_id="owner",
                organization_id="org-1",
                created_at=now,
                updated_at=now,
            )
        )
        await db.commit()
    _inviter(team)

    async def no_limit(*_args, **_kwargs) -> None:
        return None

    monkeypatch.setattr(workspaces_module, "check_rate_limit", no_limit)
    invites = InvitationService(
        Store(),
        Directories(BUILTIN),
        EngineGrantsGateway(lambda: team.iam),
        Mailer(),
        sign_in_url=lambda email, provider: f"https://web/login?email={email}",
        clock=lambda: NOW,
    )

    app = FastAPI()
    register_service_exception_handlers(app)  # as main.py does
    app.include_router(workspaces_module.router, prefix="/api/workspaces")
    app.include_router(idp_groups_router, prefix="/api/idp-groups")
    current: dict[str, Any] = {"id": "inviter"}

    async def session():
        async with nexus_db() as db:
            yield db
            await db.commit()

    app.dependency_overrides[get_db] = session
    app.dependency_overrides[invites_runtime.get_invitation_service] = lambda: invites
    app.dependency_overrides[workspaces_module._get_email_service] = lambda: None
    app.dependency_overrides[get_current_user_required] = lambda: SimpleNamespace(
        id=current["id"], email=f"{current['id']}@example.com", name=current["id"].title()
    )

    def as_(user: str) -> AsyncClient:
        current["id"] = user
        return AsyncClient(transport=ASGITransport(app=app), base_url="http://t")

    return SimpleNamespace(as_=as_, invites=invites)


def _pending(team) -> list[tuple[str, str | None]]:
    with as_service_account("engine"):
        return [(g.policy_id, g.scope) for g in team.iam.list_pending_grants()]


def _refused(response, policy_id: str) -> None:
    """A 403 carrying IAM's refusal: the policy, and the action and resource of
    it the caller does not hold."""
    assert response.status_code == 403, response.text
    detail = response.json()["detail"]
    assert detail.startswith(REFUSAL), detail
    assert f"of {policy_id} allows" in detail, detail
    assert re.search(r"allows \w+:\w+ on abi:org-1:ws-1:\S+ at abi:org-1:ws-1,", detail), detail
    assert detail.endswith("you do not hold it there"), detail


@pytest.mark.asyncio
async def test_an_invitation_to_a_role_the_inviter_lacks_is_a_403_naming_it(api, team):
    async with api.as_("inviter") as client:
        response = await client.post(
            "/api/workspaces/ws-1/members/invite",
            json={"email": "eve@example.com", "role": "member"},
        )
        _refused(response, "builtin.member")
        assert _pending(team) == []
        assert api.invites.persistence.rows == {}
        # A role it holds, it gives.
        response = await client.post(
            "/api/workspaces/ws-1/members/invite",
            json={"email": "eve@example.com", "role": "viewer"},
        )
        assert response.status_code == 200, response.text
    assert _pending(team) == [("builtin.viewer", WS1)]
    async with api.as_("admin") as client:
        response = await client.post(
            "/api/workspaces/ws-1/members/invite",
            json={"email": "bob@example.com", "role": "member"},
        )
        assert response.status_code == 200, response.text


@pytest.mark.asyncio
async def test_an_idp_binding_to_a_role_the_binder_lacks_is_a_403_naming_it(api, team):
    binding = {"provider": "builtin", "group": "Sales", "role": "member"}
    async with api.as_("inviter") as client:
        response = await client.put("/api/idp-groups/workspaces/ws-1", json=binding)
        _refused(response, "builtin.member")
    assert await api.invites.bindings([WS1]) == []
    async with api.as_("admin") as client:
        response = await client.put("/api/idp-groups/workspaces/ws-1", json=binding)
        assert response.status_code == 200, response.text
        assert [b["group"] for b in response.json()["bindings"]] == ["Sales"]
