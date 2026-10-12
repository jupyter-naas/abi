"""Pick the RemoteAppDirectory for this API process from the engine's NATS config."""

from __future__ import annotations

from typing import Any

from naas_abi.apps.nexus.apps.api.app.services.agents.remote.factory import (
    CALLER_IDENTITY,
)
from naas_abi.apps.nexus.apps.api.app.services.apps.remote.adapters.discovery import (
    DiscoveryRemoteAppDirectory,
)
from naas_abi.apps.nexus.apps.api.app.services.apps.remote.adapters.in_memory import (
    InMemoryRemoteAppDirectory,
)
from naas_abi.apps.nexus.apps.api.app.services.apps.remote.port import RemoteAppDirectory

# Above the module's own 60 s per request (naas_abi_sdk.app_host).
REQUEST_TIMEOUT_SECONDS = 65

_directory: RemoteAppDirectory | None = None


def build_remote_app_directory(nats: Any | None) -> RemoteAppDirectory:
    """Empty unless the engine runs NATS with discovery (``nats.discovery``)."""
    if nats is None or getattr(nats, "discovery", None) is None:
        return InMemoryRemoteAppDirectory()

    def clients() -> tuple[Any, Any, str]:
        from naas_abi_core.engine.nats_auth import issue_service_token
        from naas_abi_sdk.discovery import DiscoveryClient
        from naas_abi_sdk.transport import Transport

        transport = Transport(
            nats.nats_url,
            lambda: issue_service_token(CALLER_IDENTITY, nats.jwt_secret),
            timeout=REQUEST_TIMEOUT_SECONDS,
        )
        project = nats.discovery.project
        return DiscoveryClient(transport, project), transport, project

    return DiscoveryRemoteAppDirectory(clients)


def get_remote_app_directory() -> RemoteAppDirectory:
    global _directory
    if _directory is None:
        from naas_abi.apps.nexus.apps.api.app.services.agents.remote.factory import (
            _engine_nats_configuration,
        )

        _directory = build_remote_app_directory(_engine_nats_configuration())
    return _directory
