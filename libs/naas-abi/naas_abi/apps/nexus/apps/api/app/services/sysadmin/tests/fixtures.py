"""The deployment the contracts describe, as domain values (shared by adapter tests)."""

from __future__ import annotations

from naas_abi.apps.nexus.apps.api.app.services.sysadmin.port import (
    EndpointStats,
    EngineModule,
    JetStreamConsumer,
    JetStreamStream,
    JetStreamSummary,
    JobSummary,
    MicroServiceInstance,
    NatsConnection,
    NatsServer,
    RemoteModuleInstance,
    ServiceConfiguration,
)


def configured_services() -> list[ServiceConfiguration]:
    return [
        ServiceConfiguration("document", ("postgresql",)),
        ServiceConfiguration("secret", ("dotenv", "naas")),
        ServiceConfiguration("cache", ("redis:hot", "fs:cold")),
        ServiceConfiguration("kv", ("redis",)),
        ServiceConfiguration("bus", ("nats",)),
    ]


def engine_modules() -> list[EngineModule]:
    nightly = JobSummary("nightly", "", ("every 1h",), 1, 1, None)
    return [
        EngineModule(
            "acme.jobs", "Acme jobs", "", agents=1, orchestrations=0, ontologies=0, jobs=(nightly,)
        ),
        EngineModule("acme.quiet", "", "", agents=0, orchestrations=0, ontologies=0),
    ]


def _endpoint(service: str, requests: int) -> EndpointStats:
    return EndpointStats("get", f"abi.svc.{service}.v1.get", requests, 0, 1.5 if requests else 0.0)


def micro_instances() -> list[MicroServiceInstance]:
    return [
        MicroServiceInstance(
            "document", "d1", "1.0.0", "2026-10-02T08:00:00Z", (_endpoint("document", 3),)
        ),
        MicroServiceInstance(
            "document", "d2", "1.0.0", "2026-10-02T08:00:00Z", (_endpoint("document", 2),)
        ),
        MicroServiceInstance(
            "keyvalue", "k1", "1.0.0", "2026-10-02T08:00:00Z", (_endpoint("keyvalue", 0),)
        ),
    ]


def remote_instances() -> list[RemoteModuleInstance]:
    digest = JobSummary("digest", "Counts runs.", ("every 10m",), 1, 1, 60.0)
    return [
        RemoteModuleInstance(
            "ops.researcher",
            "r-1",
            "0.1.0",
            1,
            "READY",
            1_900_000_000.0,
            ("Researcher",),
            (digest,),
        ),
        RemoteModuleInstance(
            "ops.orchestrator", "o-1", "0.1.0", 1, "STARTING", 1_900_000_000.0, ("Orchestrator",)
        ),
    ]


def nats_server() -> NatsServer:
    return NatsServer(
        server_id="NSRV",
        server_name="nats",
        version="2.14.7",
        uptime="1h",
        connections=2,
        total_connections=9,
        subscriptions=40,
        slow_consumers=0,
        in_msgs=10,
        out_msgs=12,
        in_bytes=100,
        out_bytes=120,
        mem_bytes=1024,
        cpu_percent=0.5,
        max_payload=8 << 20,
        jetstream=True,
    )


def nats_connections() -> list[NatsConnection]:
    return [
        NatsConnection(
            1, "api", "10.0.0.2", 51000, "python3", "2.16.0", "1h", "1ms", 12, 0, 5, 6, 50, 60
        ),
        NatsConnection(
            2, "", "10.0.0.3", 51001, "python3", "2.16.0", "5m", "2ms", 3, 0, 1, 1, 10, 10
        ),
    ]


def jetstream() -> JetStreamSummary:
    return JetStreamSummary(
        streams=(
            JetStreamStream("KV_ABI_DISCOVERY_zen", ("$KV.ABI_DISCOVERY_zen.>",), 1, 300, 1, 1, 0),
            JetStreamStream(
                "ABI_JOBS_zen",
                ("abi.jobs.zen.>",),
                4,
                900,
                1,
                4,
                1,
                (JetStreamConsumer("job-a-b", "abi.jobs.zen.trigger.a.b", 1, 0, 0, 0),),
            ),
        ),
        memory_bytes=0,
        storage_bytes=1200,
        api_requests=30,
        api_errors=0,
    )
