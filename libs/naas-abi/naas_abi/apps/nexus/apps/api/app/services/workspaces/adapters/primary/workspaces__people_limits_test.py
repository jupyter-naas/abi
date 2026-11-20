"""The member routes that mail someone keep to the invite limits: the inviting
user's and the address's counters, a person's resend once a window, and the
organization's day of invitation mail. A request the route refuses before the
mail (unknown person, already a member) spends nothing past the inviter's own
counter. The routes, a SQLite database, real IAM and the real rate limiter (on
its own table); the people service is the in-memory one."""

from __future__ import annotations

from dataclasses import replace

import pytest
import pytest_asyncio
from naas_abi.apps.nexus.apps.api.app.services import rate_limit
from naas_abi.apps.nexus.apps.api.app.services.organizations.adapters.primary import (
    organizations__primary_adapter__FastAPI as organizations_module,
)
from naas_abi.apps.nexus.apps.api.app.services.workspaces.adapters.primary import (
    workspaces__primary_adapter__FastAPI as workspaces_module,
)
from naas_abi.apps.nexus.apps.api.app.services.workspaces.adapters.primary.workspaces__people_routes_test import (  # noqa: E501
    api,  # noqa: F401 - the fixture
)
from sqlalchemy import text
from sqlalchemy.ext.asyncio import create_async_engine


@pytest_asyncio.fixture
async def limited(api, monkeypatch):  # noqa: F811 - the fixture imported above
    """``api`` with the real limits: a few attempts a window, a small day quota."""
    engine = create_async_engine("sqlite+aiosqlite://")
    async with engine.begin() as conn:
        await conn.execute(
            text(
                "CREATE TABLE rate_limit_events "
                "(id TEXT PRIMARY KEY, identifier TEXT, endpoint TEXT, created_at TIMESTAMP)"
            )
        )
    monkeypatch.setattr(rate_limit, "async_engine", engine)
    monkeypatch.setattr(rate_limit.settings, "rate_limit_enabled", True)
    monkeypatch.setattr(rate_limit.settings, "rate_limit_attempts", 3)
    monkeypatch.setattr(rate_limit.settings, "invitation_mails_per_day", 100)
    for module in (workspaces_module, organizations_module):
        monkeypatch.setattr(module, "check_rate_limit", rate_limit.check_rate_limit)
        monkeypatch.setattr(
            module, "check_invitation_mail_quota", rate_limit.check_invitation_mail_quota
        )
    yield api
    await engine.dispose()


async def _counted(identifier: str) -> list[str]:
    async with rate_limit.async_engine.begin() as conn:
        rows = await conn.execute(
            text("SELECT endpoint FROM rate_limit_events WHERE identifier = :i"),
            {"i": identifier},
        )
        return sorted(r.endpoint for r in rows)


@pytest.mark.asyncio
async def test_adding_someone_counts_against_the_inviter_the_address_and_the_org(limited) -> None:
    async with limited.as_("admin") as http:
        added = await http.post(
            "/api/workspaces/ws-1/members", json={"user_id": "flora", "role": "viewer"}
        )
    assert added.status_code == 201, added.text
    invite = "/api/workspaces/members/invite"
    assert await _counted("user:admin") == [invite]
    assert await _counted("email:flora@example.com") == [invite]
    assert await _counted("org:org-1") == [rate_limit.INVITATION_MAIL]


@pytest.mark.asyncio
async def test_an_address_counts_as_one_whatever_its_case(limited) -> None:
    """A row from before the people directory may keep its email's capitals: its
    counter is the invite route's, which lowercases the address."""
    limited.people.users["flora"] = replace(
        limited.people.users["flora"], email="Flora@Example.com"
    )
    async with limited.as_("admin") as http:
        added = await http.post(
            "/api/workspaces/ws-1/members", json={"user_id": "flora", "role": "viewer"}
        )
    assert added.status_code == 201, added.text
    assert await _counted("email:flora@example.com") == ["/api/workspaces/members/invite"]


@pytest.mark.asyncio
async def test_an_address_is_added_or_invited_a_few_times_a_window_whoever_asks(
    limited, monkeypatch
) -> None:
    monkeypatch.setattr(rate_limit.settings, "rate_limit_attempts", 1)
    async with limited.as_("admin") as http:
        first = await http.post(
            "/api/workspaces/ws-1/members", json={"user_id": "flora", "role": "viewer"}
        )
    async with limited.as_("owner") as http:
        # Flora's address had its attempt: the owner's add of her elsewhere waits.
        again = await http.post(
            "/api/workspaces/ws-2/members", json={"user_id": "flora", "role": "viewer"}
        )
    assert first.status_code == 201, first.text
    assert again.status_code == 429, again.text
    assert len(limited.people.named("add_existing")) == 1


@pytest.mark.asyncio
async def test_a_refused_add_spends_only_the_inviters_counter(limited) -> None:
    async with limited.as_("admin") as http:
        outside = await http.post(
            "/api/workspaces/ws-1/members", json={"user_id": "outsider", "role": "viewer"}
        )
        already = await http.post(
            "/api/workspaces/ws-1/members", json={"user_id": "member", "role": "viewer"}
        )
    assert (outside.status_code, already.status_code) == (404, 409)
    assert await _counted("email:outsider@example.com") == []
    assert await _counted("email:member@example.com") == []
    assert await _counted("org:org-1") == []
    assert len(await _counted("user:admin")) == 2


@pytest.mark.asyncio
async def test_the_inviters_counter_stops_adds_and_invites_alike(limited) -> None:
    async with limited.as_("admin") as http:
        codes = [
            (
                await http.post(
                    "/api/workspaces/ws-1/members/invite",
                    json={"email": f"new{i}@example.org", "role": "viewer"},
                )
            ).status_code
            for i in range(3)
        ]
        add = await http.post(
            "/api/workspaces/ws-1/members", json={"user_id": "flora", "role": "viewer"}
        )
    assert codes == [200, 200, 200]
    assert add.status_code == 429
    assert limited.people.named("add_existing") == []


@pytest.mark.asyncio
async def test_a_person_is_sent_their_mail_again_once_a_window(limited) -> None:
    limited.people.invited("viewer")
    async with limited.as_("admin") as http:
        first = await http.post("/api/workspaces/ws-1/members/viewer/resend")
        # The same person through the organization: the same counter.
        again = await http.post("/api/organizations/org-1/members/viewer/resend")
    assert first.status_code == 200, first.text
    assert again.status_code == 429, again.text
    assert len(limited.people.named("resend")) == 1
    assert await _counted("email:viewer@example.com") == ["/api/workspaces/members/invite"]
    assert await _counted("org:org-1") == [rate_limit.INVITATION_MAIL]


@pytest.mark.asyncio
async def test_an_organizations_day_of_mail_stops_resends(limited, monkeypatch) -> None:
    monkeypatch.setattr(rate_limit.settings, "invitation_mails_per_day", 1)
    for user in ("viewer", "member"):
        limited.people.invited(user)
    async with limited.as_("admin") as http:
        first = await http.post("/api/organizations/org-1/members/viewer/resend")
        second = await http.post("/api/organizations/org-1/members/member/resend")
    assert first.status_code == 200, first.text
    assert second.status_code == 429, second.text
    assert len(limited.people.named("resend")) == 1


@pytest.mark.asyncio
async def test_resending_outside_the_scope_is_not_found_and_spends_nothing(limited) -> None:
    async with limited.as_("admin") as http:
        ws = await http.post("/api/workspaces/ws-1/members/outsider/resend")
        org = await http.post("/api/organizations/org-1/members/outsider/resend")
    assert ws.status_code == org.status_code == 404
    assert await _counted("invitation:outsider") == []
    assert await _counted("email:outsider@example.com") == []
    assert limited.people.named("resend") == []
