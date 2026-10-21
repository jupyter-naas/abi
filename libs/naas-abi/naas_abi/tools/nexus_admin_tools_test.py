"""Unit tests for Nexus admin agent tools (authz + identity, no live DB)."""

from __future__ import annotations

from typing import Any
from unittest.mock import AsyncMock, MagicMock, patch

from naas_abi_core.services.agent.context import agent_user_id, agent_workspace_id

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
    ws_token = agent_workspace_id.set("ws-1")
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
        agent_workspace_id.reset(ws_token)

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
        hashed_password="x",
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
        email=None,
        organization="Acme",
        job_title="CTO",
        bio=None,
    )
