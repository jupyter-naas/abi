"""Build the SysAdminService for this API process from the engine it runs in."""

from __future__ import annotations

import asyncio
import weakref
from collections.abc import Callable
from typing import Any

from naas_abi.apps.nexus.apps.api.app.services.sysadmin.adapters.secondary.discovery_registry import (
    DiscoveryModuleRegistry,
)
from naas_abi.apps.nexus.apps.api.app.services.sysadmin.adapters.secondary.engine_configuration import (
    EngineServiceConfiguration,
)
from naas_abi.apps.nexus.apps.api.app.services.sysadmin.adapters.secondary.engine_modules import (
    EngineModules,
)
from naas_abi.apps.nexus.apps.api.app.services.sysadmin.adapters.secondary.fallback_tap import (
    FallbackTap,
)
from naas_abi.apps.nexus.apps.api.app.services.sysadmin.adapters.secondary.in_memory import (
    UnavailableSource,
)
from naas_abi.apps.nexus.apps.api.app.services.sysadmin.adapters.secondary.jaeger_traffic_tap import (
    JaegerSpanTap,
)
from naas_abi.apps.nexus.apps.api.app.services.sysadmin.adapters.secondary.nats_http_monitor import (
    NatsHttpMonitor,
)
from naas_abi.apps.nexus.apps.api.app.services.sysadmin.adapters.secondary.nats_micro import (
    NatsMicroServiceMonitor,
)
from naas_abi.apps.nexus.apps.api.app.services.sysadmin.adapters.secondary.nats_traffic_tap import (
    NatsTrafficTap,
)
from naas_abi.apps.nexus.apps.api.app.services.sysadmin.port import (
    SourceUnavailable,
    TelemetryInfo,
)
from naas_abi.apps.nexus.apps.api.app.services.sysadmin.service import SysAdminService
from naas_abi.apps.nexus.apps.api.app.services.sysadmin.traffic import TrafficHub

# Same service identity as the API's other NATS calls (remote agents).
CALLER_IDENTITY = "api"
CONNECTION_NAME = "nexus-api-sysadmin"
TAP_CONNECTION_NAME = "nexus-api-traffic-tap"

_service: SysAdminService | None = None
_hubs: Any = None


class _PerLoop:
    """SDK transports are bound to the loop that created them: one per loop."""

    def __init__(self, factory: Callable[[], Any]) -> None:
        self._factory = factory
        self._values: weakref.WeakKeyDictionary[asyncio.AbstractEventLoop, Any] = (
            weakref.WeakKeyDictionary()
        )

    def get(self) -> Any:
        loop = asyncio.get_running_loop()
        if loop not in self._values:
            self._values[loop] = self._factory()
        return self._values[loop]


class _UnavailableTap:
    source = "nats"

    def __init__(self, reason: str) -> None:
        self.reason = reason

    async def start(self, emit: Any) -> None:
        raise SourceUnavailable("nats", self.reason)

    async def stop(self) -> None:
        return None


def _transport(nats: Any, name: str) -> Any:
    from naas_abi_core.engine.nats_auth import issue_service_token
    from naas_abi_sdk.transport import Transport

    return Transport(
        nats.nats_url,
        lambda: issue_service_token(CALLER_IDENTITY, nats.jwt_secret),
        timeout=10,
        name=name,
        connect_timeout=2,
    )


def _trace_query_url(configuration: Any) -> str | None:
    telemetry = getattr(configuration, "telemetry", None)
    if telemetry is None or not getattr(telemetry, "enabled", False):
        return None
    return getattr(telemetry, "query_url", None) or getattr(telemetry, "ui_url", None)


def build_traffic_hub(engine: Any) -> TrafficHub:
    """Traces first (tracing backend configured and reachable), else the NATS tap
    on its own connection (it receives every reply on the bus)."""
    factories: list[Any] = []
    query_url = _trace_query_url(engine.configuration)
    if query_url:
        factories.append(lambda: JaegerSpanTap(query_url))
    nats = getattr(engine.configuration, "nats", None)
    if nats is None:
        factories.append(lambda: _UnavailableTap("NATS mode is off"))
    else:
        transports = _PerLoop(lambda: _transport(nats, TAP_CONNECTION_NAME))

        async def connect() -> Any:
            return await transports.get().connect()

        factories.append(lambda: NatsTrafficTap(connect))
    return TrafficHub(lambda: FallbackTap(factories))


def telemetry_info(configuration: Any) -> TelemetryInfo:
    telemetry = getattr(configuration, "telemetry", None)
    if telemetry is None or not getattr(telemetry, "enabled", False):
        return TelemetryInfo(enabled=False, service_name="", ui_url=None)
    return TelemetryInfo(True, telemetry.service_name, telemetry.ui_url)


def build_sysadmin_service(engine: Any) -> SysAdminService:
    configuration = engine.configuration
    nats = getattr(configuration, "nats", None)
    parts: dict[str, Any] = {
        "configuration": EngineServiceConfiguration(configuration.services),
        "engine_modules": EngineModules(lambda: engine.modules),
        "telemetry": telemetry_info(configuration),
    }
    if nats is None:
        off = "NATS mode is off"
        return SysAdminService(
            **parts,
            micro=UnavailableSource("nats", off),
            registry=UnavailableSource("discovery", off),
            monitor=UnavailableSource("nats_monitor", off),
        )

    transports = _PerLoop(lambda: _transport(nats, CONNECTION_NAME))

    async def connect() -> Any:
        return await transports.get().connect()

    if nats.discovery is not None:
        project = nats.discovery.project

        def discovery_client() -> Any:
            from naas_abi_sdk.discovery import DiscoveryClient

            return DiscoveryClient(transports.get(), project)

        registry: Any = DiscoveryModuleRegistry(discovery_client)
    else:
        registry = UnavailableSource("discovery", "nats.discovery is not configured")
    monitor: Any = (
        NatsHttpMonitor(nats.monitoring_url)
        if nats.monitoring_url
        else UnavailableSource("nats_monitor", "nats.monitoring_url is not configured")
    )
    return SysAdminService(
        **parts, micro=NatsMicroServiceMonitor(connect), registry=registry, monitor=monitor
    )


def get_sysadmin_service() -> SysAdminService:
    """FastAPI dependency: one service per API process, built on first use."""
    global _service
    if _service is None:
        from naas_abi import ABIModule

        _service = build_sysadmin_service(ABIModule.get_instance().engine)
    return _service


async def get_traffic_hub() -> TrafficHub:
    """FastAPI dependency: one hub (one tap) per event loop of this API process.

    Async on purpose: FastAPI runs sync dependencies in a worker thread, where
    there is no event loop to key the hub on.
    """
    global _hubs
    if _hubs is None:
        from naas_abi import ABIModule

        engine = ABIModule.get_instance().engine
        _hubs = _PerLoop(lambda: build_traffic_hub(engine))
    return _hubs.get()
