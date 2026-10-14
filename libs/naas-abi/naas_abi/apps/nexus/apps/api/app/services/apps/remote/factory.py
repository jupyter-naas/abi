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

# Above the module's own 60 s idle limit (naas_abi_sdk.app_host).
REQUEST_TIMEOUT_SECONDS = 65
# An upload's answer waits for the whole body: the adapter stops one whose
# module stops reading, so this only bounds the longest upload.
UPLOAD_TIMEOUT_SECONDS = 24 * 3600

_directory: RemoteAppDirectory | None = None


def build_remote_app_directory(nats: Any | None) -> RemoteAppDirectory:
    """Empty unless the engine runs NATS with discovery (``nats.discovery``)."""
    if nats is None or getattr(nats, "discovery", None) is None:
        return InMemoryRemoteAppDirectory()

    def clients() -> tuple[Any, Any, Any, str]:
        from naas_abi_core.engine.nats_auth import ServiceTokenSource
        from naas_abi_sdk.discovery import DiscoveryClient
        from naas_abi_sdk.transport import Transport

        # Requests to a module's app carry a token bound to its instance; discovery
        # reads are bounded by the directory (REFRESH_SECONDS), not the transport.
        token = ServiceTokenSource(CALLER_IDENTITY, nats.jwt_secret)
        transport = Transport(nats.nats_url, token, timeout=REQUEST_TIMEOUT_SECONDS)
        uploads = Transport(nats.nats_url, token, timeout=UPLOAD_TIMEOUT_SECONDS)
        project = nats.discovery.project
        return DiscoveryClient(transport, project), transport, uploads, project

    return DiscoveryRemoteAppDirectory(clients)


def get_remote_app_directory() -> RemoteAppDirectory:
    global _directory
    if _directory is None:
        from naas_abi.apps.nexus.apps.api.app.services.agents.remote.factory import (
            _engine_nats_configuration,
        )

        _directory = build_remote_app_directory(_engine_nats_configuration())
    return _directory
