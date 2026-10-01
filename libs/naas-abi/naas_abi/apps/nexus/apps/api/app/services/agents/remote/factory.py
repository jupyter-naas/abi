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

# Discovery binds invocation status/events/cancel to the caller identity; every
# API worker shares this one so any worker can follow a run another started.
CALLER_IDENTITY = "api"

_directory: RemoteAgentDirectory | None = None


def build_remote_agent_directory(nats: Any | None) -> RemoteAgentDirectory:
    """Empty unless the engine runs NATS with discovery (``nats.discovery``)."""
    if nats is None or getattr(nats, "discovery", None) is None:
        return InMemoryRemoteAgentDirectory()

    def discovery_client() -> Any:
        from naas_abi_core.engine.nats_auth import issue_service_token
        from naas_abi_sdk.discovery import DiscoveryClient
        from naas_abi_sdk.transport import Transport

        transport = Transport(
            nats.nats_url,
            lambda: issue_service_token(CALLER_IDENTITY, nats.jwt_secret),
            timeout=30,
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
