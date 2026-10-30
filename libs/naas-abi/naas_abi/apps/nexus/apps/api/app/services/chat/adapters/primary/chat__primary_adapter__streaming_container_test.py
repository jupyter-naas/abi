"""The container a chat turn is made in: its workspace's, read from IAM."""

from __future__ import annotations

import pytest
from naas_abi.apps.nexus.apps.api.app.services.chat.adapters.primary.chat__primary_adapter__streaming import (
    turn_container,
)
from naas_abi.apps.nexus.apps.api.app.services.iam import runtime
from naas_abi.apps.nexus.apps.api.app.services.iam.names import workspace_container


@pytest.mark.asyncio
async def test_a_turn_is_made_in_its_workspace_s_container(nexus_iam):
    nexus_iam.workspace("org-1", "ws-1")
    assert await turn_container("ws-1") == workspace_container("org-1", "ws-1")
    assert await turn_container("ws-gone") is None


@pytest.mark.asyncio
async def test_without_iam_a_turn_goes_on_in_no_container():
    """IAM unavailable: no container, and IAM refuses what the turn asks; the
    stream does not fail mid-turn."""

    def unavailable():
        raise runtime.IAMUnavailableError("IAM is not available")

    previous = runtime.configure(unavailable)
    try:
        assert await turn_container("ws-1") is None
    finally:
        runtime.configure(previous)
