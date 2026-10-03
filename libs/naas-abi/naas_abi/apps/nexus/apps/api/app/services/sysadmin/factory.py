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
from naas_abi.apps.nexus.apps.api.app.services.sysadmin.adapters.secondary.jaeger_trace_store import (
    JaegerTraceStore,
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
from naas_abi.apps.nexus.apps.api.app.services.sysadmin.resources_service import (
    ResourceAdminService,
)
from naas_abi.apps.nexus.apps.api.app.services.sysadmin.service import SysAdminService
from naas_abi.apps.nexus.apps.api.app.services.sysadmin.traces import TraceStore
from naas_abi.apps.nexus.apps.api.app.services.sysadmin.traffic import TrafficHub

# Same service identity as the API's other NATS calls (remote agents).
CALLER_IDENTITY = "api"
CONNECTION_NAME = "nexus-api-sysadmin"
TAP_CONNECTION_NAME = "nexus-api-traffic-tap"
DATA_CONNECTION_NAME = "nexus-api-sysadmin-data"
JOBS_CONNECTION_NAME = "nexus-api-jobs"
TRACING_OFF = "telemetry is not enabled (telemetry.query_url)"

_service: SysAdminService | None = None
_resource_admin: ResourceAdminService | None = None
_jobs_admin: Any = None
_hubs: Any = None
_trace_store: TraceStore | SourceUnavailable | None = None


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
    return TelemetryInfo(
        True,
        telemetry.service_name,
        telemetry.ui_url,
        traces_readable=_trace_query_url(configuration) is not None,
    )


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


def _resource_source(name: str, build: Callable[[], Any]) -> Any:
    """The adapter, or why the engine cannot give the service to this API."""
    try:
        return build()
    except Exception as exc:  # noqa: BLE001 - not configured, not a dependency, failed to load
        return SourceUnavailable(name, f"{type(exc).__name__}: {exc}")


_ADAPTERS = "naas_abi.apps.nexus.apps.api.app.services.sysadmin.adapters.secondary"


def _adapter(module: str, name: str) -> Any:
    """Import lazily: a missing optional dependency only marks that service unavailable."""
    import importlib

    return getattr(importlib.import_module(f"{_ADAPTERS}.{module}"), name)


def build_resource_admin(engine: Any, audit_engine: Callable[[], Any]) -> ResourceAdminService:
    """Data browsers for every kernel service this API reaches through the engine.

    A service the engine cannot give (not configured, failed to load) is listed
    as unavailable with the reason.
    """
    services = engine.services
    builders: dict[str, Callable[[], Any]] = {
        "activity_log": lambda: _adapter("activity_log_resources", "ActivityLogResources")(
            services.activity_log,
            actor_names=_adapter("activity_log_resources", "sql_actor_names")(audit_engine),
        ),
        "cache": lambda: _adapter("cache_resources", "CacheResources")(services.cache),
        "coding_environment": lambda: _adapter(
            "coding_environment_resources", "CodingEnvironmentResources"
        )(services.coding_environment),
        "dataset": lambda: _adapter("dataset_resources", "DatasetResources")(services.dataset),
        "email": lambda: _email_resources(services.email),
        "event": lambda: _adapter("event_resources", "EventResources")(services.events),
        "document": lambda: _adapter("document_resources", "DocumentResources")(
            services.document_admin
        ),
        "keyvalue": lambda: _adapter("keyvalue_resources", "KeyValueResources")(services.kv),
        "model_registry": lambda: _adapter("model_registry_resources", "ModelRegistryResources")(
            services.model_registry
        ),
        "object_storage": lambda: _adapter("object_storage_resources", "ObjectStorageResources")(
            services.object_storage
        ),
        "secret": lambda: _adapter("secret_resources", "SecretResources")(services.secret),
        "source_control": lambda: _adapter("source_control_resources", "SourceControlResources")(
            services.source_control
        ),
        "triple_store": lambda: _adapter("triple_store_resources", "TripleStoreResources")(
            services.triple_store
        ),
        "vector_store": lambda: _adapter("vector_store_resources", "VectorStoreResources")(
            services.vector_store
        ),
    }
    sources = {name: _resource_source(name, build) for name, build in builders.items()}
    sources.update(_nats_resource_sources(engine.configuration))
    audit = _adapter("sql_audit_log", "SqlAdminAuditLog")(audit_engine)
    return ResourceAdminService(sources, audit)


def _email_resources(email: Any) -> Any:
    """Sends use the sender Nexus mails from (settings), like its own messages."""
    from naas_abi.apps.nexus.apps.api.app.core.config import settings

    return _adapter("email_resources", "EmailResources")(
        email,
        default_from=str(settings.email_from_address),
        default_from_name=settings.email_from_name,
    )


def _nats_resource_sources(configuration: Any) -> dict[str, Any]:
    """The bus (JetStream) and discovery, reached over NATS rather than the engine."""
    nats = getattr(configuration, "nats", None)
    if nats is None:
        off = "NATS mode is off"
        return {
            "bus": SourceUnavailable("bus", off),
            "discovery": SourceUnavailable("discovery", off),
        }
    transports = _PerLoop(lambda: _transport(nats, DATA_CONNECTION_NAME))

    async def connect() -> Any:
        return await transports.get().connect()

    sources: dict[str, Any] = {
        "bus": _resource_source("bus", lambda: _adapter("bus_resources", "BusResources")(connect))
    }
    if nats.discovery is None:
        sources["discovery"] = SourceUnavailable("discovery", "nats.discovery is not configured")
    else:
        project = nats.discovery.project

        def discovery_client() -> Any:
            from naas_abi_sdk.discovery import DiscoveryClient

            return DiscoveryClient(transports.get(), project)

        sources["discovery"] = _resource_source(
            "discovery",
            lambda: _adapter("discovery_resources", "DiscoveryResources")(discovery_client),
        )
    return sources


def get_resource_admin() -> ResourceAdminService:
    """FastAPI dependency: one per API process, built on first use."""
    global _resource_admin
    if _resource_admin is None:
        from naas_abi import ABIModule
        from naas_abi.apps.nexus.apps.api.app.core import database

        _resource_admin = build_resource_admin(
            ABIModule.get_instance().engine, lambda: database.async_engine
        )
    return _resource_admin


# --- jobs ------------------------------------------------------------------------------


def jobs_project(configuration: Any) -> str:
    """The project job hosts use (stream ``ABI_JOBS_<project>``, run collections)."""
    nats = getattr(configuration, "nats", None)
    discovery = getattr(nats, "discovery", None) if nats is not None else None
    return discovery.project if discovery is not None else "default"


def job_owners(engine: Any) -> dict[str, Any]:
    """What the engine hosts jobs for (``Engine.job_owners``) as the API sees it:
    the loaded modules, this platform module, and the kernel dataset jobs."""
    owners: dict[str, Any] = dict(engine.modules)
    try:
        from naas_abi import ABIModule

        owners.setdefault("naas_abi", ABIModule.get_instance())
    except Exception:  # noqa: BLE001 - not loaded (tests, standalone API)
        pass
    try:
        dataset = engine.configuration.nats is not None and engine.services.dataset_available()
    except Exception:  # noqa: BLE001
        dataset = False
    if dataset:
        from naas_abi_core.services.dataset.DatasetMaintenanceJobs import (
            DATASET_JOBS_OWNER,
            DatasetMaintenanceJobs,
        )

        owners[DATASET_JOBS_OWNER] = DatasetMaintenanceJobs
    return owners


def build_jobs_admin(engine: Any, audit_engine: Callable[[], Any]) -> Any:
    from naas_abi.apps.nexus.apps.api.app.services.sysadmin.jobs_service import (
        JobsAdminService,
    )

    configuration = engine.configuration
    nats = getattr(configuration, "nats", None)
    project = jobs_project(configuration)
    catalogs: list[Any] = [_adapter("job_catalogs", "EngineJobCatalog")(lambda: job_owners(engine))]
    if nats is None:
        off = "NATS mode is off: module jobs run on NATS"
        catalogs.append(SourceUnavailable("discovery", "NATS mode is off"))
        runs: Any = SourceUnavailable("runs", off)
        control: Any = SourceUnavailable("jobs", off)
        queue: Any = SourceUnavailable("queue", off)
    else:
        transports = _PerLoop(lambda: _transport(nats, JOBS_CONNECTION_NAME))

        async def connect() -> Any:
            return await transports.get().connect()

        if nats.discovery is not None:

            def discovery_client() -> Any:
                from naas_abi_sdk.discovery import DiscoveryClient

                return DiscoveryClient(transports.get(), project)

            catalogs.append(
                _resource_source(
                    "discovery",
                    lambda: _adapter("job_catalogs", "DiscoveryJobCatalog")(discovery_client),
                )
            )
        else:
            catalogs.append(SourceUnavailable("discovery", "nats.discovery is not configured"))
        runs = _resource_source(
            "runs",
            lambda: _adapter("document_job_runs", "DocumentJobRunStore")(
                lambda: engine.services.document_admin, project
            ),
        )
        control = _resource_source(
            "jobs", lambda: _adapter("nats_job_control", "NatsJobControl")(transports.get, project)
        )
        queue = _resource_source(
            "queue", lambda: _adapter("nats_job_queue", "NatsJobQueue")(connect, project)
        )
    return JobsAdminService(
        catalogs=catalogs,
        runs=runs,
        control=control,
        queue=queue,
        audit=_adapter("sql_audit_log", "SqlAdminAuditLog")(audit_engine),
        project=project,
        trace_ui_url=telemetry_info(configuration).ui_url,
    )


def get_jobs_admin() -> Any:
    """FastAPI dependency: one per API process, built on first use."""
    global _jobs_admin
    if _jobs_admin is None:
        from naas_abi import ABIModule
        from naas_abi.apps.nexus.apps.api.app.core import database

        _jobs_admin = build_jobs_admin(
            ABIModule.get_instance().engine, lambda: database.async_engine
        )
    return _jobs_admin


def build_trace_store(configuration: Any) -> TraceStore | SourceUnavailable:
    """Jaeger's query API when tracing is configured, else why there is none."""
    query_url = _trace_query_url(configuration)
    if not query_url:
        return SourceUnavailable("tracing", TRACING_OFF)
    return JaegerTraceStore(query_url)


def get_trace_store() -> TraceStore | SourceUnavailable:
    """FastAPI dependency: one per API process, built on first use."""
    global _trace_store
    if _trace_store is None:
        from naas_abi import ABIModule

        _trace_store = build_trace_store(ABIModule.get_instance().engine.configuration)
    return _trace_store


def get_trace_ui_url() -> str | None:
    """FastAPI dependency: the tracing backend's own UI, when configured."""
    from naas_abi import ABIModule

    return telemetry_info(ABIModule.get_instance().engine.configuration).ui_url
