from __future__ import annotations

import asyncio

from naas_abi.apps.nexus.apps.api.app.services.agents.remote.adapters.discovery import (
    DiscoveryRemoteAgentDirectory,
)
from naas_abi.apps.nexus.apps.api.app.services.agents.remote.factory import (
    build_remote_agent_directory,
)
from naas_abi_core.engine.engine_configuration.EngineConfiguration import NATSConfiguration


def test_no_nats_means_no_remote_agents():
    directory = build_remote_agent_directory(None)

    assert asyncio.run(directory.list_agents()) == []


def test_nats_without_discovery_means_no_remote_agents():
    directory = build_remote_agent_directory(NATSConfiguration(jwt_secret="s" * 48))

    assert asyncio.run(directory.list_agents()) == []


def test_discovery_builds_a_discovery_directory_for_the_project():
    nats = NATSConfiguration(
        jwt_secret="s" * 48, nats_url="nats://nats:4222", discovery={"project": "zen"}
    )

    directory = build_remote_agent_directory(nats)

    assert isinstance(directory, DiscoveryRemoteAgentDirectory)

    async def client():
        return directory._client()

    discovery = asyncio.run(client())
    assert discovery.project == "zen"
