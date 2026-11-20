"""Unit tests for Nexus admin agent tools (authz + identity, no live DB)."""

from __future__ import annotations

from contextlib import ExitStack
from typing import Any
from unittest.mock import AsyncMock, MagicMock, patch

from naas_abi_core.services.agent.context import agent_container, agent_user_id

from naas_abi.apps.nexus.apps.api.app.services.iam.names import workspace_container
from naas_abi.tools import nexus_admin_tools as mod


def _tools_by_name() -> dict[str, Any]:
    return {t.name: t for t in mod.nexus_admin_tools()}


def test_tools_require_authenticated_user() -> None:
    token = agent_user_id.set(None)
    try:
        tools = _tools_by_name()
        result = tools["list_organizations"].invoke({})
        assert isinstance(result, dict)
        assert "error" in result
        assert "signed in" in result["error"].lower()
    finally:
        agent_user_id.reset(token)


def test_create_workspace_rejects_bad_slug() -> None:
    token = agent_user_id.set("user-admin")
    try:
        tools = _tools_by_name()
        result = tools["create_workspace"].invoke(
            {
                "name": "Bad",
                "slug": "Not A Slug",
                "organization_id": "org-1",
            }
        )
        assert result["error"]
        assert "slug" in result["error"].lower()
    finally:
        agent_user_id.reset(token)


def test_invite_workspace_member_requires_admin() -> None:
    user_token = agent_user_id.set("user-member")
    ws_token = agent_container.set(workspace_container(None, "ws-1"))
    tools = _tools_by_name()

    mock_ws = MagicMock()
    mock_ws.get_workspace_role = AsyncMock(return_value="member")
    mock_ws.invite_workspace_member = AsyncMock()

    async def fake_with_db(fn):  # type: ignore[no-untyped-def]
        return await fn(MagicMock())

    try:
        with (
            patch.object(mod, "_workspace_service", return_value=mock_ws),
            patch.object(mod, "_with_db", side_effect=fake_with_db),
        ):
            result = tools["invite_workspace_member"].invoke(
                {"email": "someone@naas.ai", "role": "member"}
            )
    finally:
        agent_user_id.reset(user_token)
        agent_container.reset(ws_token)

    assert result["error"]
    assert "owners/admins" in result["error"].lower()
    mock_ws.invite_workspace_member.assert_not_called()


def test_nexus_admin_tools_exported_names() -> None:
    names = sorted(t.name for t in mod.nexus_admin_tools())
    assert "create_workspace" in names
    assert "invite_workspace_member" in names
    assert "list_organization_members" in names
    assert "update_my_profile" in names
    assert len(names) >= 10


def test_update_my_profile_writes_organization_and_job_title() -> None:
    from datetime import datetime
    from unittest.mock import create_autospec

    from naas_abi.apps.nexus.apps.api.app.services.auth.port import AuthUserRecord
    from naas_abi.apps.nexus.apps.api.app.services.auth.service import AuthService

    token = agent_user_id.set("user-1")
    tools = _tools_by_name()
    # Autospec: a call that no longer matches AuthService.update_profile fails here.
    auth = create_autospec(AuthService, instance=True)
    auth.update_profile.return_value = AuthUserRecord(
        id="user-1",
        email="a@b.c",
        name="Alice",
        created_at=datetime(2026, 1, 1),
        organization="Acme",
        job_title="CTO",
        bio=None,
    )

    async def fake_with_db(fn):  # type: ignore[no-untyped-def]
        return await fn(MagicMock())

    try:
        with (
            patch.object(mod, "_auth_service", return_value=auth),
            patch.object(mod, "_with_db", side_effect=fake_with_db),
        ):
            result = tools["update_my_profile"].invoke(
                {"organization": " Acme ", "job_title": "CTO"}
            )
    finally:
        agent_user_id.reset(token)

    assert result["status"] == "updated"
    assert result["user"]["organization"] == "Acme"
    assert result["user"]["job_title"] == "CTO"
    auth.update_profile.assert_awaited_once_with(
        user_id="user-1",
        name=None,
        organization="Acme",
        job_title="CTO",
        bio=None,
    )


class _People:
    """The people service the tools call: records what it was asked."""

    def __init__(self, error: Exception | None = None) -> None:
        self.asked: list[dict[str, Any]] = []
        self.error = error

    async def create_or_link(self, **kwargs: Any) -> Any:
        from naas_abi.apps.nexus.apps.api.app.services.workspaces.people_port import (
            CreateOrLinkResult,
            PlatformUser,
            UserStatus,
        )

        self.asked.append(kwargs)
        if self.error is not None:
            raise self.error
        return CreateOrLinkResult(
            user=PlatformUser("usr-9", kwargs["email"], None, UserStatus.ACTIVE, "builtin"),
            created=False,
            provisioned=False,
            sign_in_email_sent=True,
            warning=None,
        )


def _invoke_with(
    people: Any, tool: str, args: dict[str, Any], *, limited: Any = None, **services: Any
) -> Any:
    async def fake_with_db(fn):  # type: ignore[no-untyped-def]
        return await fn(MagicMock())

    limits = AsyncMock(return_value=limited)

    auth = MagicMock()
    auth.get_user = AsyncMock(return_value=MagicMock(email="me@naas.ai", name="Me"))
    token = agent_user_id.set("user-admin")
    try:
        with ExitStack() as stack:
            stack.enter_context(patch.object(mod, "_people_service", return_value=people))
            stack.enter_context(patch.object(mod, "_auth_service", return_value=auth))
            stack.enter_context(patch.object(mod, "_with_db", side_effect=fake_with_db))
            stack.enter_context(patch.object(mod, "_invite_limits", limits))
            for name, service in services.items():
                stack.enter_context(patch.object(mod, name, return_value=service))
            return _tools_by_name()[tool].invoke(args)
    finally:
        agent_user_id.reset(token)


def _workspaces(role: str = "admin") -> MagicMock:
    ws = MagicMock()
    ws.get_workspace_role = AsyncMock(return_value=role)
    ws.get_workspace = AsyncMock(return_value=MagicMock(id="ws-1", organization_id="org-1"))
    return ws


def test_invite_workspace_member_links_or_creates_with_the_workspace_role_only() -> None:
    people = _People()

    out = _invoke_with(
        people,
        "invite_workspace_member",
        {"email": "Flo@Naas.ai", "workspace_id": "ws-1", "role": "viewer"},
        _workspace_service=_workspaces(),
    )

    assert out["status"] == "added"
    assert out["user"] == {"id": "usr-9", "email": "flo@naas.ai", "name": None, "status": "active"}
    assert "user_created" not in out and "created" not in out
    (asked,) = people.asked
    assert [(g.scope, g.scope_id, g.role) for g in asked["grants"]] == [
        ("workspace", "ws-1", "viewer")
    ]
    assert asked["by"].id == "user-admin"
    assert asked["organization_id"] == "org-1"


def test_invite_organization_member_gives_the_org_and_workspace_roles() -> None:
    people = _People()
    org = MagicMock()
    org.get_organization_role = AsyncMock(return_value="admin")
    org.list_all_workspaces = AsyncMock(return_value=[MagicMock(id="ws-1")])
    org.get_organization_member = AsyncMock(return_value=None)

    out = _invoke_with(
        people,
        "invite_organization_member",
        {
            "organization_id": "org-1",
            "email": "a@naas.ai",
            "workspace_id": "ws-1",
            "workspace_role": "viewer",
        },
        _organization_service=org,
    )

    assert out["status"] == "added", out
    (asked,) = people.asked
    assert [(g.scope, g.scope_id, g.role) for g in asked["grants"]] == [
        ("organization", "org-1", "member"),
        ("workspace", "ws-1", "viewer"),
    ]
    assert asked["may_grant_owner"] is False


def test_a_refusal_of_the_people_service_is_reported_not_raised() -> None:
    from naas_abi.apps.nexus.apps.api.app.services.people.port import AlreadyMemberError

    out = _invoke_with(
        _People(AlreadyMemberError("usr-9", "already")),
        "invite_workspace_member",
        {"email": "a@naas.ai", "workspace_id": "ws-1"},
        _workspace_service=_workspaces(),
    )

    assert out == {"error": "Already a member", "email": "a@naas.ai"}


def test_an_invitation_past_the_invite_limits_is_reported_and_nobody_is_asked() -> None:
    people = _People()

    out = _invoke_with(
        people,
        "invite_workspace_member",
        {"email": "a@naas.ai", "workspace_id": "ws-1"},
        limited={
            "error": "Too many attempts. Please try again in 5 minutes.",
            "email": "a@naas.ai",
        },
        _workspace_service=_workspaces(),
    )

    assert out["error"].startswith("Too many attempts")
    assert people.asked == []


def test_the_invite_limits_are_the_routes_own(monkeypatch) -> None:
    """The asking user's and the address's counters of the invite route, and the
    organization's day of invitation mail."""
    import asyncio

    from naas_abi.apps.nexus.apps.api.app.services import rate_limit

    seen: list[tuple[Any, ...]] = []

    async def counted(identifier, endpoint, *_args, **_kwargs):
        seen.append((identifier, endpoint))

    async def quota(organization_id, workspace_id):
        seen.append(("quota", organization_id, workspace_id))

    monkeypatch.setattr(rate_limit, "check_rate_limit", counted)
    monkeypatch.setattr(rate_limit, "check_invitation_mail_quota", quota)

    out = asyncio.run(
        mod._invite_limits(
            "user-admin",
            "a@naas.ai",
            endpoint="/api/workspaces/members/invite",
            organization_id="org-1",
            workspace_id="ws-1",
        )
    )

    assert out is None
    assert seen == [
        ("user:user-admin", "/api/workspaces/members/invite"),
        ("email:a@naas.ai", "/api/workspaces/members/invite"),
        ("quota", "org-1", "ws-1"),
    ]
