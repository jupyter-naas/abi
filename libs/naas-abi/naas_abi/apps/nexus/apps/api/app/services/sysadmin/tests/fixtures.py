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


# --- service data (resources.py) -------------------------------------------------------

# What a data adapter's test seeds before running ServiceResourcesContract: three
# items at the root and, for services with containers, ``nested`` holding ``delta``.
SEED_ITEMS: dict[str, bytes] = {
    "alpha": b"first value",
    "beta": b"second value",
    "gamma": b"third value",
}
SEED_CONTAINER = "nested"
SEED_NESTED: dict[str, bytes] = {"delta": b"fourth value"}


# --- jobs (jobs.py) --------------------------------------------------------------------


def job_definitions():
    from naas_abi.apps.nexus.apps.api.app.services.sysadmin.jobs import (
        JobDefinition,
        TriggerSpec,
    )

    return [
        JobDefinition(
            "acme.jobs",
            "nightly",
            "Nightly sync.",
            "engine",
            (TriggerSpec("cron", "0 0 6 * * *", "UTC"),),
            max_concurrency=1,
            max_attempts=3,
            timeout_seconds=600.0,
        ),
        JobDefinition("acme.jobs", "sync", "", "engine", (TriggerSpec("every", "10m"),)),
        JobDefinition(
            "acme.other",
            "report",
            "",
            "remote",
            (TriggerSpec("event", "evt.1a2b3c.>"),),
            instances=2,
        ),
    ]


def job_runs():
    """Newest first across modules: sync:9, report:1, nightly:3, nightly:2."""
    from naas_abi.apps.nexus.apps.api.app.services.sysadmin.jobs import JobRun, RunTrigger

    return [
        JobRun(
            "acme.jobs",
            "nightly",
            "nightly:2",
            "FAILED",
            attempt=3,
            max_attempts=3,
            trigger=RunTrigger("schedule", "abi.jobs.zen.schedule.m.j.0"),
            fired_at="2026-10-01T06:00:00+00:00",
            started_at="2026-10-01T06:00:01+00:00",
            finished_at="2026-10-01T06:00:31+00:00",
            instance="i-1",
            error="RuntimeError: upstream 503",
            trace_id="a" * 32,
            payload={},
            logs=("starting", "upstream 503"),
        ),
        JobRun(
            "acme.jobs",
            "nightly",
            "nightly:3",
            "SUCCEEDED",
            attempt=1,
            max_attempts=3,
            trigger=RunTrigger("schedule", "abi.jobs.zen.schedule.m.j.0"),
            fired_at="2026-10-02T06:00:00+00:00",
            started_at="2026-10-02T06:00:01+00:00",
            finished_at="2026-10-02T06:00:31.500000+00:00",
            instance="i-1",
            trace_id="b" * 32,
            payload={},
            result={"rows": 3},
            logs=("synced 3 rows",),
        ),
        JobRun(
            "acme.jobs",
            "sync",
            "sync:9",
            "RUNNING",
            trigger=RunTrigger("manual"),
            fired_at="2026-10-02T09:00:00+00:00",
            started_at="2026-10-02T09:00:00.200000+00:00",
            instance="i-2",
            payload={"since": "2026-10-01"},
        ),
        JobRun(
            "acme.other",
            "report",
            "report:1",
            "TIMED_OUT",
            trigger=RunTrigger("event"),
            fired_at="2026-10-02T07:00:00+00:00",
            started_at="2026-10-02T07:00:01+00:00",
            finished_at="2026-10-02T07:01:01+00:00",
            instance="r-1",
            error="Timed out after 60s",
            payload={},
        ),
    ]


# --- traces (traces.py) ----------------------------------------------------------------

TRACE_A = "0af7651916cd43dd8448eb211c80319c"
TRACE_B = "4bf92f3577b34da6a3ce929d0e0e4736"
TRACE_C = "5b8efff798038103d269b633813fc60c"


def traces(now):
    """The ``TraceStoreContract`` deployment, ``now`` a UTC datetime:

    - A, 120 s ago: ``nexus-api`` SERVER ``GET /api/search`` (250 ms) with a
      ``zen-engine`` CLIENT child ``document/get`` (10 ms in, 200 ms, status ok,
      ``rpc.service=document``);
    - B, 60 s ago: ``ops-researcher`` CONSUMER ``digest`` (1500 ms) with an INTERNAL
      child ``fetch`` (100 ms in, 400 ms, error "boom", event ``retry`` 50 ms in
      with ``attempt=2``);
    - C, 2 h ago: ``nexus-api`` SERVER ``GET /health`` (5 ms).
    """
    from datetime import timedelta

    from naas_abi.apps.nexus.apps.api.app.services.sysadmin.traces import (
        Span,
        SpanEvent,
        Trace,
        service_counts,
    )

    def resource(service):
        return {"service.name": service}

    def trace(trace_id, ago, duration_ms, spans):
        start = (now - timedelta(seconds=ago)).isoformat()
        return Trace(trace_id, start, duration_ms, service_counts(spans), tuple(spans))

    search = Span(
        "a000000000000001",
        None,
        "GET /api/search",
        "nexus-api",
        "server",
        0.0,
        250.0,
        "unset",
        attributes={"http.request.method": "GET"},
        resource=resource("nexus-api"),
    )
    get = Span(
        "a000000000000002",
        search.span_id,
        "document/get",
        "zen-engine",
        "client",
        10.0,
        200.0,
        "ok",
        attributes={"rpc.service": "document"},
        resource=resource("zen-engine"),
    )
    digest = Span(
        "b000000000000001",
        None,
        "digest",
        "ops-researcher",
        "consumer",
        0.0,
        1500.0,
        "unset",
        resource=resource("ops-researcher"),
    )
    fetch = Span(
        "b000000000000002",
        digest.span_id,
        "fetch",
        "ops-researcher",
        "internal",
        100.0,
        400.0,
        "error",
        "boom",
        resource=resource("ops-researcher"),
        events=(SpanEvent("retry", 50.0, {"attempt": 2}),),
    )
    health = Span(
        "c000000000000001",
        None,
        "GET /health",
        "nexus-api",
        "server",
        0.0,
        5.0,
        "unset",
        resource=resource("nexus-api"),
    )
    return [
        trace(TRACE_A, 120, 250.0, [search, get]),
        trace(TRACE_B, 60, 1500.0, [digest, fetch]),
        trace(TRACE_C, 7200, 5.0, [health]),
    ]


T0_NS = 1_759_392_000_000_000_000  # 2025-10-02T08:00:00Z


def otlp_attributes(**values):
    """OTLP JSON attributes: int64 as strings, lists as arrayValue, dicts as kvlistValue."""

    def value(v):
        if isinstance(v, bool):
            return {"boolValue": v}
        if isinstance(v, int):
            return {"intValue": str(v)}
        if isinstance(v, float):
            return {"doubleValue": v}
        if isinstance(v, list):
            return {"arrayValue": {"values": [value(x) for x in v]}}
        if isinstance(v, dict):
            return {
                "kvlistValue": {"values": [{"key": k, "value": value(x)} for k, x in v.items()]}
            }
        return {"stringValue": v}

    return [{"key": k, "value": value(v)} for k, v in values.items()]


def otlp_span(
    trace_id,
    span_id,
    name,
    *,
    parent="",
    kind=1,
    start_ms=0.0,
    duration_ms=1.0,
    status=None,
    attributes=None,
    events=(),
    links=(),
):
    start = T0_NS + int(start_ms * 1e6)
    return {
        "traceId": trace_id,
        "spanId": span_id,
        "parentSpanId": parent,
        "name": name,
        "kind": kind,
        "startTimeUnixNano": str(start),
        "endTimeUnixNano": str(start + int(duration_ms * 1e6)),
        "attributes": otlp_attributes(**(attributes or {})),
        "events": [
            {
                "timeUnixNano": str(start + int(offset * 1e6)),
                "name": event,
                "attributes": otlp_attributes(**attrs),
            }
            for event, offset, attrs in events
        ],
        "links": [{"traceId": t, "spanId": s} for t, s in links],
        "status": status or {},
    }


def otlp_resource(service, *spans, **resource):
    return {
        "resource": {"attributes": otlp_attributes(**{"service.name": service}, **resource)},
        "scopeSpans": [{"scope": {"name": "naas_abi"}, "spans": list(spans)}],
    }


OTLP_TRACE = "4bf92f3577b34da6a3ce929d0e0e4736"


def otlp_response():
    """One trace as Jaeger's ``/api/v3/traces`` answers it, every case at once:

    ``root`` (nexus-api SERVER, 100 ms) and ``early`` (zen-engine CLIENT child,
    same start, error status "boom", an event 2 ms in and a link); ``late``
    (zen-engine INTERNAL child of ``root`` 40 ms in, ``error=true`` tag only);
    ``orphan`` (zen-engine, parent ``ffffffffffffffff`` not in the trace, 30 ms in,
    running 90 ms so the trace lasts 120 ms). ``root`` carries every attribute type.
    """
    root = otlp_span(
        OTLP_TRACE,
        "00f067aa0ba902b7",
        "GET /api/search",
        kind=2,
        duration_ms=100.0,
        status={"code": 1},
        attributes={
            "http.request.method": "GET",
            "http.response.status_code": 200,
            "abi.cached": False,
            "abi.ratio": 0.5,
            "abi.tags": ["a", "b"],
            "abi.labels": {"team": "ops"},
        },
    )
    early = otlp_span(
        OTLP_TRACE,
        "00f067aa0ba902b8",
        "document/get",
        parent="00f067aa0ba902b7",
        kind=3,
        duration_ms=20.0,
        status={"code": 2, "message": "boom"},
        events=[("retry", 2.0, {"attempt": 2})],
        links=[("5b8efff798038103d269b633813fc60c", "5fb397be34d26b51")],
    )
    late = otlp_span(
        OTLP_TRACE,
        "00f067aa0ba902b9",
        "rank",
        parent="00f067aa0ba902b7",
        start_ms=40.0,
        duration_ms=10.0,
        attributes={"error": True},
    )
    orphan = otlp_span(
        OTLP_TRACE,
        "00f067aa0ba902ba",
        "flush",
        parent="ffffffffffffffff",
        start_ms=30.0,
        duration_ms=90.0,
    )
    return {
        "result": {
            "resourceSpans": [
                otlp_resource("nexus-api", root, **{"deployment.environment": "dev"}),
                otlp_resource("zen-engine", late, orphan, early),
            ]
        }
    }


def agent_runs():
    """Newest first across modules: r4 (running), r3, r2, r1."""
    from naas_abi.apps.nexus.apps.api.app.services.sysadmin.agents import AgentRun

    return [
        AgentRun(
            "acme.agents",
            "r1",
            "Researcher",
            "inv-1",
            "CANCELLED",
            thread_id="t-1",
            caller="orchestrator",
            owner="i-1",
            submitted_at="2026-10-01T09:00:00+00:00",
            finished_at="2026-10-01T09:00:05+00:00",
            error_code="CANCELLED",
            error_message="Execution stopped; completed side effects are not undone",
            events=1,
        ),
        AgentRun(
            "acme.agents",
            "r2",
            "Researcher",
            "inv-2",
            "SUCCEEDED",
            thread_id="t-2",
            caller="api",
            owner="i-1",
            submitted_at="2026-10-02T09:00:00+00:00",
            finished_at="2026-10-02T09:00:12.500000+00:00",
            trace_id="c" * 32,
            events=3,
        ),
        AgentRun(
            "acme.other",
            "r3",
            "Writer",
            "inv-3",
            "FAILED",
            thread_id="t-3",
            caller="api",
            owner="w-1",
            submitted_at="2026-10-02T10:00:00+00:00",
            finished_at="2026-10-02T10:00:01+00:00",
            error_code="AGENT_FAILED",
            error_message="Agent execution failed; inspect provider logs",
        ),
        AgentRun(
            "acme.agents",
            "r4",
            "Researcher",
            "inv-4",
            "RUNNING",
            thread_id="t-4",
            caller="orchestrator",
            owner="i-2",
            submitted_at="2026-10-02T11:00:00+00:00",
            events=1,
        ),
    ]


def agent_events():
    """Each run's events in order, as (event, text)."""
    return {
        ("acme.agents", "r1"): [("message", "Starting")],
        ("acme.agents", "r2"): [
            ("message", "Looking it up"),
            ("message", "x" * 1500),
            ("done", "[DONE]"),
        ],
        ("acme.agents", "r4"): [("message", "Working")],
    }
