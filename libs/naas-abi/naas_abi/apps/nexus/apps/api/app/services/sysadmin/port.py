"""SysAdmin domain: what a platform super admin can see of a running ABI deployment.

Read-only views of the engine (configured kernel services, loaded modules) and of
the NATS network (micro-service stats, discovered remote modules, server,
connections, JetStream). Each source is a port; adapters live in
``adapters/secondary`` and are validated by the contracts in ``contracts.py``.
No transport or framework types cross these ports.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Protocol


class SourceUnavailable(Exception):
    """A source cannot answer (NATS mode off, broker or monitor unreachable)."""

    def __init__(self, source: str, reason: str) -> None:
        super().__init__(f"{source} unavailable: {reason}")
        self.source = source
        self.reason = reason


# --- engine ----------------------------------------------------------------------------


@dataclass(frozen=True)
class ServiceConfiguration:
    """A kernel service as configured in the engine: adapter kinds only, never settings."""

    name: str
    adapters: tuple[str, ...]


@dataclass(frozen=True)
class JobSummary:
    name: str
    description: str
    triggers: tuple[str, ...]
    max_concurrency: int
    max_attempts: int
    timeout_seconds: float | None


@dataclass(frozen=True)
class EngineModule:
    """A module loaded in this engine process."""

    module_id: str
    name: str
    description: str
    agents: int
    orchestrations: int
    ontologies: int
    jobs: tuple[JobSummary, ...] = ()


# --- NATS ------------------------------------------------------------------------------


@dataclass(frozen=True)
class EndpointStats:
    name: str
    subject: str
    requests: int
    errors: int
    average_ms: float
    last_error: str = ""


@dataclass(frozen=True)
class MicroServiceInstance:
    """One running instance of a NATS micro service (``$SRV.STATS``)."""

    name: str
    instance_id: str
    version: str
    started: str
    endpoints: tuple[EndpointStats, ...]

    @property
    def requests(self) -> int:
        return sum(e.requests for e in self.endpoints)

    @property
    def errors(self) -> int:
        return sum(e.errors for e in self.endpoints)


@dataclass(frozen=True)
class RemoteModuleInstance:
    """A module instance registered in NATS discovery."""

    module_id: str
    instance_id: str
    package_version: str
    contract_major: int
    status: str
    expires_at: float
    agents: tuple[str, ...]
    jobs: tuple[JobSummary, ...] = ()


@dataclass(frozen=True)
class NatsServer:
    server_id: str
    server_name: str
    version: str
    uptime: str
    connections: int
    total_connections: int
    subscriptions: int
    slow_consumers: int
    in_msgs: int
    out_msgs: int
    in_bytes: int
    out_bytes: int
    mem_bytes: int
    cpu_percent: float
    max_payload: int
    jetstream: bool


@dataclass(frozen=True)
class NatsConnection:
    cid: int
    name: str
    ip: str
    port: int
    lang: str
    version: str
    uptime: str
    rtt: str
    subscriptions: int
    pending_bytes: int
    in_msgs: int
    out_msgs: int
    in_bytes: int
    out_bytes: int


@dataclass(frozen=True)
class JetStreamConsumer:
    name: str
    filter_subject: str
    pending: int
    ack_pending: int
    redelivered: int
    waiting: int


@dataclass(frozen=True)
class JetStreamStream:
    name: str
    subjects: tuple[str, ...]
    messages: int
    bytes: int
    first_seq: int
    last_seq: int
    consumer_count: int
    consumers: tuple[JetStreamConsumer, ...] = ()

    @property
    def kind(self) -> str:
        """What ABI uses the stream for, from its naming scheme."""
        if self.name.startswith("KV_"):
            return "kv"
        if self.name.startswith("ABI_JOBS_"):
            return "jobs"
        if self.name.startswith("naas-abi-"):
            return "bus"
        return "other"


@dataclass(frozen=True)
class JetStreamSummary:
    streams: tuple[JetStreamStream, ...]
    memory_bytes: int
    storage_bytes: int
    api_requests: int
    api_errors: int

    @property
    def consumers(self) -> int:
        return sum(s.consumer_count for s in self.streams)

    @property
    def messages(self) -> int:
        return sum(s.messages for s in self.streams)


# --- ports -----------------------------------------------------------------------------


class ServiceConfigurationSource(Protocol):
    async def list_configured(self) -> list[ServiceConfiguration]: ...


class EngineModuleSource(Protocol):
    async def list_modules(self) -> list[EngineModule]: ...


class MicroServiceMonitor(Protocol):
    async def list_instances(self) -> list[MicroServiceInstance]:
        """Every instance answering ``$SRV.STATS``. Raises SourceUnavailable."""
        ...


class ModuleRegistry(Protocol):
    async def list_instances(self) -> list[RemoteModuleInstance]:
        """Every live instance in discovery. Raises SourceUnavailable."""
        ...


class NatsServerMonitor(Protocol):
    """The broker's HTTP monitoring endpoint. Every method raises SourceUnavailable."""

    async def server(self) -> NatsServer: ...

    async def connections(self, *, limit: int = 256) -> list[NatsConnection]: ...

    async def jetstream(self) -> JetStreamSummary: ...


# --- views the use cases return --------------------------------------------------------


@dataclass(frozen=True)
class KernelService:
    """A kernel service: its configuration merged with its live NATS instances."""

    name: str
    adapters: tuple[str, ...]
    nats_service: str | None
    instances: tuple[MicroServiceInstance, ...] = ()

    @property
    def status(self) -> str:
        if self.nats_service is None:
            return "not_exposed"
        return "serving" if self.instances else "silent"


@dataclass(frozen=True)
class TelemetryInfo:
    """Tracing as configured for this engine (``telemetry:``); ``ui_url`` opens traces."""

    enabled: bool
    service_name: str
    ui_url: str | None


@dataclass(frozen=True)
class SourceStatus:
    available: bool
    reason: str = ""


@dataclass(frozen=True)
class KernelServicesView:
    services: tuple[KernelService, ...]
    sources: dict[str, SourceStatus]


@dataclass(frozen=True)
class ModulesView:
    engine: tuple[EngineModule, ...]
    remote: tuple[RemoteModuleInstance, ...]
    sources: dict[str, SourceStatus]


@dataclass(frozen=True)
class Overview:
    sources: dict[str, SourceStatus]
    kernel_services: int
    serving_services: int
    service_instances: int
    requests: int
    engine_modules: int
    remote_modules: dict[str, int] = field(default_factory=dict)
    server: NatsServer | None = None
    jetstream_streams: int = 0
    jetstream_consumers: int = 0
    jetstream_messages: int = 0
    telemetry: TelemetryInfo | None = None
