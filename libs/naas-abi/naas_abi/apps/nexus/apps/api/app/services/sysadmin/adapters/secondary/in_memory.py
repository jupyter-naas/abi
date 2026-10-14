"""In-memory adapters: fixed data for tests and for deployments without a source."""

from __future__ import annotations

from naas_abi.apps.nexus.apps.api.app.services.sysadmin.port import (
    EngineModule,
    JetStreamSummary,
    MicroServiceInstance,
    NatsConnection,
    NatsServer,
    RemoteModuleInstance,
    ServiceConfiguration,
    SourceUnavailable,
)


class InMemoryServiceConfiguration:
    def __init__(self, services: list[ServiceConfiguration]) -> None:
        self._services = list(services)

    async def list_configured(self) -> list[ServiceConfiguration]:
        return list(self._services)


class InMemoryEngineModules:
    def __init__(self, modules: list[EngineModule]) -> None:
        self._modules = list(modules)

    async def list_modules(self) -> list[EngineModule]:
        return list(self._modules)


class InMemoryMicroServiceMonitor:
    def __init__(self, instances: list[MicroServiceInstance]) -> None:
        self._instances = list(instances)

    async def list_instances(self) -> list[MicroServiceInstance]:
        return list(self._instances)


class InMemoryModuleRegistry:
    def __init__(self, instances: list[RemoteModuleInstance]) -> None:
        self._instances = list(instances)

    async def list_instances(self) -> list[RemoteModuleInstance]:
        return list(self._instances)


class InMemoryNatsServerMonitor:
    def __init__(
        self, server: NatsServer, connections: list[NatsConnection], jetstream: JetStreamSummary
    ) -> None:
        self._server, self._connections, self._jetstream = server, list(connections), jetstream

    async def server(self) -> NatsServer:
        return self._server

    async def connections(self, *, limit: int = 256) -> list[NatsConnection]:
        return self._connections[:limit]

    async def jetstream(self) -> JetStreamSummary:
        return self._jetstream


class UnavailableSource:
    """Stands in for any NATS-side port when it cannot exist (e.g. NATS mode off)."""

    def __init__(self, source: str, reason: str) -> None:
        self.source, self.reason = source, reason

    def _raise(self):
        raise SourceUnavailable(self.source, self.reason)

    async def list_instances(self):
        self._raise()

    async def server(self):
        self._raise()

    async def connections(self, *, limit: int = 256):
        self._raise()

    async def jetstream(self):
        self._raise()
