"""resolve_provider routes agents published by remote modules to the remote stream."""

from __future__ import annotations

import asyncio
from types import SimpleNamespace
from unittest.mock import AsyncMock

from naas_abi.apps.nexus.apps.api.app.services.chat.port import ChatAgentRecord
from naas_abi.apps.nexus.apps.api.app.services.chat.service import ChatService


def test_remote_agent_resolves_to_the_remote_provider() -> None:
    service = ChatService(adapter=AsyncMock())
    # The real record get_agent returns: no module_path, unlike AgentRecord.
    agent = ChatAgentRecord(
        id="a-9",
        workspace_id="ws",
        name="Researcher",
        class_name="acme.research/Researcher",
        model_id=None,
        provider="remote",
    )
    service.get_agent = AsyncMock(return_value=agent)  # type: ignore[method-assign]

    resolved = asyncio.run(
        service.resolve_provider(
            context=None, provider=None, has_images=False, agent_id="a-9", workspace_id="ws"
        )
    )

    assert resolved is not None
    assert (resolved.type, resolved.model) == ("remote", "acme.research/Researcher")
    assert resolved.enabled


def test_resolved_remote_provider_passes_the_request_schema() -> None:
    from naas_abi.apps.nexus.apps.api.app.services.chat.adapters.primary.chat__primary_adapter__schemas import (
        ProviderConfigRequest,
    )

    config = ProviderConfigRequest(
        id="remote-a-9",
        name="Remote (acme.research)",
        type="remote",
        enabled=True,
        model="acme.research/Researcher",
    )

    assert config.type == "remote"


def test_a_client_cannot_pick_a_remote_agent_through_the_provider_payload() -> None:
    service = ChatService(adapter=AsyncMock())
    service.get_agent = AsyncMock(return_value=None)  # type: ignore[method-assign]
    forged = SimpleNamespace(
        id="x",
        name="x",
        type="remote",
        enabled=True,
        endpoint=None,
        api_key=None,
        account_id=None,
        model="acme.research/Researcher",
        llm_model=None,
    )

    resolved = asyncio.run(
        service.resolve_provider(context=None, provider=forged, has_images=False, agent_id=None)
    )

    assert resolved is None or resolved.type != "remote"


def test_remote_agents_get_only_the_first_turn_user_profile() -> None:
    service = ChatService(adapter=AsyncMock())
    service.build_user_context_addendum = AsyncMock(return_value="User: Ada, data engineer.")  # type: ignore[method-assign]
    first_turn = [SimpleNamespace(role="user", content="hi")]
    later_turn = [*first_turn, SimpleNamespace(role="assistant", content="hello")]

    assert asyncio.run(service.build_remote_agent_preamble(first_turn, "u-1", "ws", "c-1")) == (
        "User: Ada, data engineer."
    )
    assert asyncio.run(service.build_remote_agent_preamble(later_turn, "u-1", "ws", "c-1")) is None
