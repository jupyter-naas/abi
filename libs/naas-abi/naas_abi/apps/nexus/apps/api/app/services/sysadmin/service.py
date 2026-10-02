"""SysAdmin use cases: combine the sources into the views the dashboard shows.

Each source can be down independently (NATS mode off, broker or monitor
unreachable): views still answer, and say which source is missing and why.
"""

from __future__ import annotations

import asyncio
from collections import Counter
from typing import Any, TypeVar

from naas_abi.apps.nexus.apps.api.app.services.sysadmin.port import (
    EngineModuleSource,
    JetStreamSummary,
    KernelService,
    KernelServicesView,
    MicroServiceInstance,
    MicroServiceMonitor,
    ModuleRegistry,
    ModulesView,
    NatsConnection,
    NatsServer,
    NatsServerMonitor,
    Overview,
    ServiceConfigurationSource,
    SourceStatus,
    SourceUnavailable,
    TelemetryInfo,
)

# Engine configuration name -> NATS micro service name. None: not a micro service
# (the bus is JetStream; the model registry uses plain subscriptions).
NATS_SERVICE_NAMES: dict[str, str | None] = {
    "kv": "keyvalue",
    "bus": None,
    "model_registry": None,
}

T = TypeVar("T")

NO_TELEMETRY = TelemetryInfo(enabled=False, service_name="", ui_url=None)


async def _attempt(source: str, call: Any, fallback: T) -> tuple[T, SourceStatus]:
    try:
        return await call, SourceStatus(True)
    except SourceUnavailable as exc:
        return fallback, SourceStatus(False, exc.reason)


def merge_services(
    configured: list[Any], instances: list[MicroServiceInstance]
) -> tuple[KernelService, ...]:
    by_name: dict[str, list[MicroServiceInstance]] = {}
    for instance in instances:
        by_name.setdefault(instance.name, []).append(instance)
    services = []
    claimed: set[str] = set()
    for service in configured:
        nats_name = NATS_SERVICE_NAMES.get(service.name, service.name)
        if nats_name is not None:
            claimed.add(nats_name)
        services.append(
            KernelService(
                name=service.name,
                adapters=service.adapters,
                nats_service=nats_name,
                instances=tuple(by_name.get(nats_name, ())) if nats_name else (),
            )
        )
    for name in sorted(set(by_name) - claimed):
        services.append(KernelService(name, (), name, tuple(by_name[name])))
    return tuple(services)


class SysAdminService:
    def __init__(
        self,
        *,
        configuration: ServiceConfigurationSource,
        engine_modules: EngineModuleSource,
        micro: MicroServiceMonitor,
        registry: ModuleRegistry,
        monitor: NatsServerMonitor,
        telemetry: TelemetryInfo = NO_TELEMETRY,
    ) -> None:
        self.configuration = configuration
        self.engine_modules = engine_modules
        self.micro = micro
        self.registry = registry
        self.monitor = monitor
        self.telemetry = telemetry

    async def kernel_services(self) -> KernelServicesView:
        configured, (instances, nats) = await asyncio.gather(
            self.configuration.list_configured(),
            _attempt("nats", self.micro.list_instances(), []),
        )
        return KernelServicesView(merge_services(configured, instances), {"nats": nats})

    async def modules(self) -> ModulesView:
        engine, (remote, discovery) = await asyncio.gather(
            self.engine_modules.list_modules(),
            _attempt("discovery", self.registry.list_instances(), []),
        )
        return ModulesView(tuple(engine), tuple(remote), {"discovery": discovery})

    async def nats_server(self) -> NatsServer:
        return await self.monitor.server()

    async def nats_connections(self, *, limit: int = 256) -> list[NatsConnection]:
        return await self.monitor.connections(limit=limit)

    async def jetstream(self) -> JetStreamSummary:
        return await self.monitor.jetstream()

    async def overview(self) -> Overview:
        (
            configured,
            engine,
            (instances, nats),
            (remote, discovery),
            (server, server_status),
            (jetstream, _),
        ) = await asyncio.gather(
            self.configuration.list_configured(),
            self.engine_modules.list_modules(),
            _attempt("nats", self.micro.list_instances(), []),
            _attempt("discovery", self.registry.list_instances(), []),
            _attempt("nats_monitor", self.monitor.server(), None),
            _attempt("nats_monitor", self.monitor.jetstream(), None),
        )
        services = merge_services(configured, instances)
        return Overview(
            sources={
                "engine": SourceStatus(True),
                "nats": nats,
                "discovery": discovery,
                "nats_monitor": server_status,
            },
            kernel_services=len(configured),
            serving_services=sum(1 for s in services if s.status == "serving" and s.adapters),
            service_instances=len(instances),
            requests=sum(i.requests for i in instances),
            engine_modules=len(engine),
            remote_modules=dict(Counter(i.status for i in remote)),
            server=server,
            jetstream_streams=len(jetstream.streams) if jetstream else 0,
            jetstream_consumers=jetstream.consumers if jetstream else 0,
            jetstream_messages=jetstream.messages if jetstream else 0,
            telemetry=self.telemetry,
        )
