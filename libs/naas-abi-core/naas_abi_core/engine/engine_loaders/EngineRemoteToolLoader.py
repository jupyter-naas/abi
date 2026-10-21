"""Publishes the tools SDK modules serve to this process's tool registry.

Config-gated: only with a ``nats.discovery`` block and ``nats.tool_registry.
remote_modules.enabled`` (the default). Every role that composes agents does it
(serving, standby, client), so an agent built in any of them can run a remote
tool: the registry's bindings are per process. The SDK is the core ``[nats]``
extra and is imported only here.
"""

from __future__ import annotations

from collections.abc import Collection

from naas_abi_core import logger
from naas_abi_core.engine.engine_configuration.EngineConfiguration import (
    NATSConfiguration,
)
from naas_abi_core.services.tool_registry.ToolRegistryPort import IToolRegistry


class RunningRemoteTools:
    """The synchroniser and the NATS adapter it reads and calls through."""

    def __init__(self, synchronizer, adapter) -> None:
        self._synchronizer = synchronizer
        self._adapter = adapter

    def stop(self) -> None:
        self._synchronizer.stop()
        self._adapter.close()


class EngineRemoteToolLoader:
    @classmethod
    def start(
        cls,
        nats: NATSConfiguration,
        registry: IToolRegistry,
        local_modules: Collection[str],
    ) -> RunningRemoteTools | None:
        settings = nats.tool_registry.remote_modules
        if nats.discovery is None or not settings.enabled:
            logger.debug("Remote tools: no discovery or disabled, none published")
            return None
        from naas_abi_core.services.tool_registry.adapters.primary.RemoteToolBinding import (
            RemoteToolBinding,
        )
        from naas_abi_core.services.tool_registry.adapters.secondary.RemoteToolsSecondaryAdapterNATS import (
            RemoteToolsSecondaryAdapterNATS,
        )
        from naas_abi_core.services.tool_registry.RemoteToolSynchronizer import (
            RemoteToolSynchronizer,
        )

        adapter = RemoteToolsSecondaryAdapterNATS(
            nats.nats_url,
            nats.jwt_secret,
            nats.discovery.project,
            call_timeout_seconds=settings.call_timeout_seconds,
        )
        synchronizer = RemoteToolSynchronizer(
            registry,
            adapter,
            lambda definition, major: RemoteToolBinding(definition, major, adapter),
            reserved=local_modules,
            refresh_seconds=settings.refresh_seconds,
        )
        synchronizer.start()
        return RunningRemoteTools(synchronizer, adapter)
