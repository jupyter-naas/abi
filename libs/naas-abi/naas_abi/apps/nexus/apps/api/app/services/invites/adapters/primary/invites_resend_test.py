"""Resending an invitation is rate limited like inviting, once a window per
invitation, within the organization's day of invitation mail; the mail's subject
carries nothing an organization's people wrote. Real route, invitation service,
rate limiter (SQLite) and IAM."""

from __future__ import annotations

from types import SimpleNamespace
from typing import Any

import pytest
import pytest_asyncio
from fastapi import FastAPI
from httpx import ASGITransport, AsyncClient
from naas_abi.apps.nexus.apps.api.app.core.database import get_db
from naas_abi.apps.nexus.apps.api.app.models import OrganizationModel, UserModel
from naas_abi.apps.nexus.apps.api.app.services import rate_limit
from naas_abi.apps.nexus.apps.api.app.services.auth.adapters.primary.auth__primary_adapter__dependencies import (  # noqa: E501
    get_current_user_required,
)
from naas_abi.apps.nexus.apps.api.app.services.invites import runtime as invites_runtime
from naas_abi.apps.nexus.apps.api.app.services.invites.adapters.primary.invites__primary_adapter__FastAPI import (  # noqa: E501
    invitations_router,
)
from naas_abi.apps.nexus.apps.api.app.services.invites.adapters.secondary.engine import (
    EngineGrantsGateway,
)
from naas_abi.apps.nexus.apps.api.app.services.invites.invitation_email import (
    render_invitation,
)
from naas_abi.apps.nexus.apps.api.app.services.invites.port import InvitationMail
from naas_abi.apps.nexus.apps.api.app.services.invites.service import InvitationService
from naas_abi.apps.nexus.apps.api.app.services.invites.service_test import (
    BUILTIN,
    NOW,
    Directories,
    Mailer,
    Store,
)
from sqlalchemy import text
from sqlalchemy.ext.asyncio import create_async_engine

ORG_NAME = "Acme Holdings, see https://example.invalid/about for who we are"


@pytest_asyncio.fixture
async def api(team, nexus_db, monkeypatch):
    async with nexus_db() as db:
        db.add(UserModel(id="owner", email="owner@example.com", name="Owner"))
        db.add(OrganizationModel(id="org-1", name=ORG_NAME, slug="org", owner_id="owner"))
        await db.commit()
    limits = create_async_engine("sqlite+aiosqlite://")
    async with limits.begin() as conn:
        await conn.execute(
            text(
                "CREATE TABLE rate_limit_events "
                "(id TEXT PRIMARY KEY, identifier TEXT, endpoint TEXT, created_at TIMESTAMP)"
            )
        )
    monkeypatch.setattr(rate_limit, "async_engine", limits)
    monkeypatch.setattr(rate_limit.settings, "rate_limit_enabled", True)
    mailer = Mailer()
    invites = InvitationService(
        Store(),
        Directories(BUILTIN),
        EngineGrantsGateway(lambda: team.iam),
        mailer,
        sign_in_url=lambda email, provider: f"https://web/login?email={email}",
        clock=lambda: NOW,
    )

    async def invite(email: str) -> str:
        outcome = await invites.invite(
            email=email,
            name=None,
            provider=None,
            organization_id="org-1",
            org_role="member",
            workspace_id=None,
            workspace_role=None,
            invited_by=None,
        )
        return outcome.invitation.id

    app = FastAPI()
    app.include_router(invitations_router, prefix="/api/invitations")

    async def session():
        async with nexus_db() as db:
            yield db
            await db.commit()

    app.dependency_overrides[get_db] = session
    app.dependency_overrides[invites_runtime.get_invitation_service] = lambda: invites
    current: dict[str, Any] = {"id": "owner"}
    app.dependency_overrides[get_current_user_required] = lambda: SimpleNamespace(
        id=current["id"], email=f"{current['id']}@example.com", name=current["id"].title()
    )

    def as_(user: str) -> AsyncClient:
        current["id"] = user
        return AsyncClient(transport=ASGITransport(app=app), base_url="http://t")

    yield SimpleNamespace(as_=as_, invite=invite, mailer=mailer)
    await limits.dispose()


@pytest.mark.asyncio
async def test_resending_an_invitation_keeps_to_its_rate_limit(api) -> None:
    invitation = await api.invite("someone@example.com")
    sent_before = len(api.mailer.sent)
    async with api.as_("owner") as http:
        first = await http.post(f"/api/invitations/{invitation}/resend")
        again = [await http.post(f"/api/invitations/{invitation}/resend") for _ in range(5)]
    assert first.status_code == 200, first.text
    assert {r.status_code for r in again} == {429}
    assert len(api.mailer.sent) == sent_before + 1


@pytest.mark.asyncio
async def test_a_refused_resend_spends_none_of_the_inviters_budget(api, monkeypatch) -> None:
    monkeypatch.setattr(rate_limit.settings, "rate_limit_attempts", 2)
    first = await api.invite("first@example.com")
    second = await api.invite("second@example.com")
    async with api.as_("owner") as http:
        assert (await http.post(f"/api/invitations/{first}/resend")).status_code == 200
        refused = [await http.post(f"/api/invitations/{first}/resend") for _ in range(5)]
        other = await http.post(f"/api/invitations/{second}/resend")
    assert {r.status_code for r in refused} == {429}
    assert other.status_code == 200, other.text


@pytest.mark.asyncio
async def test_an_organizations_invitation_mail_keeps_to_its_day_quota(api, monkeypatch) -> None:
    monkeypatch.setattr(rate_limit.settings, "invitation_mails_per_day", 2)
    monkeypatch.setattr(rate_limit.settings, "rate_limit_attempts", 100)
    invitations = [await api.invite(f"person{i}@example.com") for i in range(3)]
    async with api.as_("owner") as http:
        codes = [(await http.post(f"/api/invitations/{i}/resend")).status_code for i in invitations]
    assert codes == [200, 200, 429]


def test_the_invitation_subject_keeps_tenant_text_out() -> None:
    mail = InvitationMail(
        to_email="someone@example.com",
        provider=BUILTIN,
        inviter_name="IT Helpdesk " + "x" * 300,
        organization_name=ORG_NAME,
        organization_role="member",
        workspace_name=None,
        workspace_role=None,
        sign_in_url="https://web/login",
    )
    subject, body, html = render_invitation(mail, app_name="Nexus")
    assert subject == "You are invited to Nexus"
    # In the body, what the organization's people wrote is quoted and cut short.
    assert f"“{ORG_NAME}”" in body
    assert "x" * 100 not in body and "x" * 100 not in html
