"""The organization drives a user may open, as ``/api/workspaces`` shows them."""

from __future__ import annotations

import pytest
from naas_abi.apps.nexus.apps.api.app.services.iam import runtime
from naas_abi.apps.nexus.apps.api.app.services.iam.user_features import organization_drives


@pytest.mark.asyncio
async def test_the_organizations_people_may_open_its_drive_and_nobody_else(team) -> None:
    for user in ("owner", "admin", "member", "viewer"):
        assert await organization_drives(user, {"org-1"}) == {"org-1"}, user
    assert await organization_drives("stranger", {"org-1"}) == set()
    # A role in one of its workspaces alone does not reach the organization's drive.
    team.grant("ws-only", "member", team.workspace("org-1", "ws-1"))
    assert await organization_drives("ws-only", {"org-1"}) == set()
    assert await organization_drives("owner", set()) == set()


@pytest.mark.asyncio
async def test_a_deny_at_the_organization_hides_its_drive(team) -> None:
    team.deny(
        "member",
        ["nexus:ListOrgFiles"],
        ["${scope}/nexus:file/organization"],
        team.org("org-1"),
    )
    assert await organization_drives("member", {"org-1"}) == set()


@pytest.mark.asyncio
async def test_without_iam_no_drive_is_shown() -> None:
    previous = runtime.configure(lambda: None)
    try:
        assert await organization_drives("owner", {"org-1"}) == set()
    finally:
        runtime.configure(previous)
