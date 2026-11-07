"""Pick the RemoteAppDirectory for this API process from the engine's NATS config."""

from __future__ import annotations

from typing import Any

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
        from naas_abi.apps.nexus.apps.api.app.services.engine_credentials import (
            api_delegate,
            api_host_token,
            api_token,
        )
        from naas_abi_sdk.discovery import DiscoveryClient
        from naas_abi_sdk.transport import Transport

        token = api_token()
        host_token = api_host_token()

        # For the signed-in user: the request to the app host carries a delegation
        # naming the app's module and the user, which the host forwards to
        # discovery to learn who is calling (never from HttpRequest.user_id).
        transport = Transport(
            nats.nats_url,
            token,
            timeout=REQUEST_TIMEOUT_SECONDS,
            delegate=api_delegate(),
            host_token=host_token,
        )
        uploads = Transport(
            nats.nats_url,
            token,
            timeout=UPLOAD_TIMEOUT_SECONDS,
            delegate=api_delegate(),
            host_token=host_token,
        )
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
