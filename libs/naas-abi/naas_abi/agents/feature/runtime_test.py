"""A feature agent's tools ask IAM what the routes ask, as the user."""

from __future__ import annotations

import pytest
from naas_abi.agents.feature.runtime import request_context, require_action
from naas_abi.apps.nexus.apps.api.app.services.iam.testing import NexusIam


@pytest.fixture
def world():
    nexus = NexusIam()
    scope = nexus.workspace("org-1", "ws-1")
    for user in ("owner", "member", "viewer"):
        nexus.grant(user, user, scope)
    nexus.user("stranger")
    with nexus.installed():
        yield nexus


@pytest.mark.asyncio
async def test_a_tool_is_allowed_what_the_users_role_allows(world) -> None:
    assert await require_action("viewer", "ws-1", "ListSkills") is None
    assert await require_action("viewer", "ws-1", "CreateSkill") is not None
    assert await require_action("member", "ws-1", "CreateSkill") is None
    assert await require_action("member", "ws-1", "UpdateSkill", id="skill-1") is None
    assert await require_action("stranger", "ws-1", "ListSkills") is not None
    assert await require_action("owner", "ws-2", "ListSkills") is not None


def test_a_request_context_names_the_asker() -> None:
    assert request_context("user-1").actor_user_id == "user-1"
