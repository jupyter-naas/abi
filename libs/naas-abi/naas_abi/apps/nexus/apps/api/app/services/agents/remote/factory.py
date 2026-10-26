"""Pick the RemoteAgentDirectory for this API process from the engine's NATS config."""

from __future__ import annotations

from typing import Any

from naas_abi.apps.nexus.apps.api.app.services.agents.remote.adapters.discovery import (
    DiscoveryRemoteAgentDirectory,
)
from naas_abi.apps.nexus.apps.api.app.services.agents.remote.adapters.in_memory import (
    InMemoryRemoteAgentDirectory,
)
from naas_abi.apps.nexus.apps.api.app.services.agents.remote.port import RemoteAgentDirectory

# Nexus calls remote agents and apps for the signed-in user with a delegation
# that names the module behind the host as the actor and the user:
# discovery checks the user's policy and the module's (discovery:InvokeAgent,
# OpenApp) and makes the user the owner of the runs it starts, so any API worker
# can follow them. The host holds a token that is good for that module acting
# for that user, ten minutes, and nowhere else; never ``api``'s own.

_directory: RemoteAgentDirectory | None = None


def build_remote_agent_directory(nats: Any | None) -> RemoteAgentDirectory:
    """Empty unless the engine runs NATS with discovery (``nats.discovery``)."""
    if nats is None or getattr(nats, "discovery", None) is None:
        return InMemoryRemoteAgentDirectory()

    def discovery_client() -> Any:
        from naas_abi.apps.nexus.apps.api.app.services.engine_credentials import (
            api_delegate,
            api_host_token,
            api_token,
        )
        from naas_abi_sdk.discovery import DiscoveryClient
        from naas_abi_sdk.transport import Transport

        # api's own tokens (engine_credentials) for what Nexus asks for itself
        # (listing agents); for a call made for the signed-in user, a delegation:
        # to discovery with api as the actor, to a host with its module.
        transport = Transport(
            nats.nats_url,
            api_token(),
            timeout=30,
            delegate=api_delegate(),
            host_token=api_host_token(),
        )
        return DiscoveryClient(transport, nats.discovery.project)

    return DiscoveryRemoteAgentDirectory(discovery_client)


def get_remote_agent_directory() -> RemoteAgentDirectory:
    global _directory
    if _directory is None:
        _directory = build_remote_agent_directory(_engine_nats_configuration())
    return _directory


def _engine_nats_configuration() -> Any | None:
    try:
        from naas_abi import ABIModule

        return ABIModule.get_instance().engine.configuration.nats
    except Exception:  # noqa: BLE001 - no engine (tests, tooling): no remote agents
        return None
