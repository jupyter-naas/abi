from __future__ import annotations

from types import SimpleNamespace

import pytest
from naas_abi.apps.nexus.apps.api.app.services.workspaces.service import (
    WorkspacePermissionError,
    WorkspaceService,
)


@pytest.mark.asyncio
async def test_the_role_is_the_one_iam_holds(team) -> None:
    service = WorkspaceService(adapter=SimpleNamespace())

    assert await service.get_workspace_role(user_id="member", workspace_id="ws-1") == "member"
    assert await service.get_workspace_role(user_id="stranger", workspace_id="ws-1") is None
    assert await service.get_workspace_role(user_id="member", workspace_id="ws-unknown") is None


@pytest.mark.asyncio
async def test_a_platform_admin_administers_every_workspace(team) -> None:
    """``builtin.platform_admin`` covers every container: their role in a workspace is
    admin, with no group of it (the access move leaves them none)."""
    team.platform_admin("root")
    service = WorkspaceService(adapter=SimpleNamespace())

    assert await service.get_workspace_role(user_id="root", workspace_id="ws-1") == "admin"
    rows = [SimpleNamespace(id="ws-1", organization_id="org-1")]
    assert await service.effective_roles("root", rows) == ["admin"]
    assert await service.effective_roles("member", rows) == ["member"]


@pytest.mark.asyncio
async def test_require_workspace_access_raises_when_missing_role(team) -> None:
    service = WorkspaceService(adapter=SimpleNamespace())

    with pytest.raises(WorkspacePermissionError):
        await service.require_workspace_access(user_id="stranger", workspace_id="ws-1")


def _people():
    from naas_abi.apps.nexus.apps.api.app.services.workspaces.people_testing import (
        FakePeopleService,
    )

    return FakePeopleService.of(
        ("owner", "owner@acme.io", "Olga"),
        ("admin", "admin@acme.io", "Adam"),
        ("member", "member@acme.io", "Flo Member"),
        ("flo", "florent@acme.io", "Florent"),
        ("flo2", "florent.other@gmail.com", "Florent Two"),
        ("outsider", "florent@other.io", "Florent Outside"),
    )


def _users_adapter():
    from unittest.mock import AsyncMock

    from naas_abi.apps.nexus.apps.api.app.services.workspaces.port import UserRecord

    return SimpleNamespace(
        get_users_by_ids=AsyncMock(
            side_effect=lambda ids: {
                i: UserRecord(id=i, email=f"{i}@acme.io", avatar=f"/a/{i}.png") for i in ids
            }
        )
    )


@pytest.fixture
def directory(team):
    """ws-2 in org-1: ``flo`` holds a role in ws-2 only, ``flo2`` is an org member,
    ``outsider`` belongs to another organization."""
    ws2 = team.workspace("org-1", "ws-2")
    team.grant("flo", "viewer", ws2)
    team.grant("flo2", "member", team.org("org-1"))
    team.grant("outsider", "member", team.workspace("org-9", "ws-9"))
    team.workspace(None, "ws-solo")
    return team


@pytest.mark.asyncio
async def test_candidates_are_org_directory_people_not_in_the_workspace(directory) -> None:
    service = WorkspaceService(adapter=_users_adapter())
    people = _people()

    found = await service.member_candidates("ws-1", "flo", people=people)

    # ``member`` (in ws-1 already) and ``outsider`` (another org) never show.
    assert [(c.user_id, c.org_role, c.avatar) for c in found] == [
        ("flo2", "member", "/a/flo2.png"),
        ("flo", None, "/a/flo.png"),
    ]
    searched = people.named("search")[0]
    assert "outsider" not in searched["among"] and "member" not in searched["among"]
    # The org's owners and admins reach every workspace: never candidates.
    assert {"owner", "admin"}.isdisjoint(searched["among"])


@pytest.mark.asyncio
async def test_candidates_need_two_characters_and_an_organization(directory) -> None:
    service = WorkspaceService(adapter=_users_adapter())
    people = _people()

    assert await service.member_candidates("ws-1", "f", people=people) == []
    assert await service.member_candidates("ws-1", "  f ", people=people) == []
    assert await service.member_candidates("ws-solo", "flo", people=people) == []
    assert await service.member_candidates("ws-unknown", "flo", people=people) == []
    assert people.named("search") == []


@pytest.mark.asyncio
async def test_candidates_are_capped(directory) -> None:
    service = WorkspaceService(adapter=_users_adapter())
    people = _people()

    await service.member_candidates("ws-1", "flo", people=people, limit=500)
    await service.member_candidates("ws-1", "flo", people=people, limit=1)

    assert [c["limit"] for c in people.named("search")] == [20, 1]


@pytest.mark.asyncio
async def test_a_search_result_outside_the_directory_is_dropped(directory) -> None:
    """Whatever the people service answers, only the org directory is shown."""
    service = WorkspaceService(adapter=_users_adapter())
    people = _people()

    async def leaky(*, q, among, limit=10):
        return list(people.users.values())

    people.search = leaky  # type: ignore[method-assign]

    found = await service.member_candidates("ws-1", "flo", people=people)

    assert {c.user_id for c in found} == {"flo", "flo2"}


@pytest.mark.asyncio
async def test_directory_entry_is_the_persons_place_in_the_workspaces_org(directory) -> None:
    service = WorkspaceService(adapter=SimpleNamespace())

    entry = await service.directory_entry("ws-1", "flo")
    assert entry is not None and entry.workspace_ids == ("ws-2",)
    assert await service.directory_entry("ws-1", "outsider") is None
    assert await service.directory_entry("ws-solo", "flo") is None
