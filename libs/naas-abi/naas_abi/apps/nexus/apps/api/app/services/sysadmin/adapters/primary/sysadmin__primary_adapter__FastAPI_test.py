import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from naas_abi.apps.nexus.apps.api.app.services.auth.adapters.primary.auth__primary_adapter__dependencies import (
    get_current_user_required,
)
from naas_abi.apps.nexus.apps.api.app.services.auth.adapters.primary.auth__primary_adapter__schemas import (
    User,
)
from naas_abi.apps.nexus.apps.api.app.services.sysadmin.adapters.primary.sysadmin__primary_adapter__FastAPI import (
    router,
)
from naas_abi.apps.nexus.apps.api.app.services.sysadmin.adapters.secondary.in_memory import (
    InMemoryEngineModules,
    InMemoryMicroServiceMonitor,
    InMemoryModuleRegistry,
    InMemoryNatsServerMonitor,
    InMemoryServiceConfiguration,
    UnavailableSource,
)
from naas_abi.apps.nexus.apps.api.app.services.sysadmin.factory import get_sysadmin_service
from naas_abi.apps.nexus.apps.api.app.services.sysadmin.service import SysAdminService
from naas_abi.apps.nexus.apps.api.app.services.sysadmin.tests import fixtures


def _service(monitor=None):
    return SysAdminService(
        configuration=InMemoryServiceConfiguration(fixtures.configured_services()),
        engine_modules=InMemoryEngineModules(fixtures.engine_modules()),
        micro=InMemoryMicroServiceMonitor(fixtures.micro_instances()),
        registry=InMemoryModuleRegistry(fixtures.remote_instances()),
        monitor=monitor
        or InMemoryNatsServerMonitor(
            fixtures.nats_server(), fixtures.nats_connections(), fixtures.jetstream()
        ),
    )


def _client(*, is_superadmin=True, service=None):
    app = FastAPI()
    app.include_router(router, prefix="/api/admin/system")
    app.dependency_overrides[get_current_user_required] = lambda: User.model_construct(
        id="u1", email="u1@example.com", name="U1", is_superadmin=is_superadmin
    )
    app.dependency_overrides[get_sysadmin_service] = lambda: service or _service()
    return TestClient(app)


PATHS = [
    "/overview",
    "/services",
    "/modules",
    "/telemetry",
    "/nats/server",
    "/nats/connections",
    "/nats/jetstream",
]


@pytest.mark.parametrize("path", PATHS)
def test_every_view_is_superadmin_only(path):
    response = _client(is_superadmin=False).get(f"/api/admin/system{path}")

    assert response.status_code == 403


def test_overview():
    body = _client().get("/api/admin/system/overview").json()

    assert body["kernel_services"] == 5 and body["requests"] == 5
    assert body["remote_modules"] == {"READY": 1, "STARTING": 1}
    assert body["server"]["version"] == "2.14.7"
    assert body["sources"]["nats"] == {"available": True, "reason": ""}


def test_services_include_status_and_instance_totals():
    body = _client().get("/api/admin/system/services").json()
    services = {s["name"]: s for s in body["services"]}

    assert services["document"]["status"] == "serving"
    assert [i["requests"] for i in services["document"]["instances"]] == [3, 2]
    assert services["bus"]["status"] == "not_exposed"


def test_modules():
    body = _client().get("/api/admin/system/modules").json()

    assert [m["module_id"] for m in body["engine"]] == ["acme.jobs", "acme.quiet"]
    researcher = next(m for m in body["remote"] if m["module_id"] == "ops.researcher")
    assert researcher["jobs"][0]["triggers"] == ["every 10m"]


def test_jetstream_streams_carry_their_kind_and_totals():
    body = _client().get("/api/admin/system/nats/jetstream").json()

    assert {s["name"]: s["kind"] for s in body["streams"]} == {
        "KV_ABI_DISCOVERY_zen": "kv",
        "ABI_JOBS_zen": "jobs",
    }
    assert (body["consumers"], body["messages"]) == (1, 5)


def test_connections_respect_the_limit():
    body = _client().get("/api/admin/system/nats/connections?limit=1").json()

    assert [c["name"] for c in body] == ["api"]


def test_an_unavailable_source_is_a_503_naming_it():
    service = _service(
        monitor=UnavailableSource("nats_monitor", "nats.monitoring_url is not configured")
    )

    response = _client(service=service).get("/api/admin/system/nats/server")

    assert response.status_code == 503
    assert response.json()["detail"] == {
        "source": "nats_monitor",
        "reason": "nats.monitoring_url is not configured",
    }


class _Tap:
    source = "nats"

    def __init__(self, events=(), unavailable=None):
        self.events, self.unavailable = list(events), unavailable

    async def start(self, emit):
        if self.unavailable:
            from naas_abi.apps.nexus.apps.api.app.services.sysadmin.port import SourceUnavailable

            raise SourceUnavailable("nats", self.unavailable)
        for event in self.events:
            emit(event)

    async def stop(self):
        pass


def _stream_frames(tap, query="max_seconds=1"):
    import json

    from naas_abi.apps.nexus.apps.api.app.services.sysadmin.factory import get_traffic_hub
    from naas_abi.apps.nexus.apps.api.app.services.sysadmin.traffic import TrafficHub

    client = _client()
    client.app.dependency_overrides[get_traffic_hub] = lambda: TrafficHub(lambda: tap)
    frames = []
    with client.stream("GET", f"/api/admin/system/traffic/stream?{query}") as response:
        assert response.status_code == 200
        assert response.headers["content-type"].startswith("text/event-stream")
        for line in response.iter_lines():
            if line.startswith("data: "):
                frames.append(json.loads(line[6:]))
    return frames


def test_traffic_stream_sends_status_then_batches_then_ends():
    from naas_abi.apps.nexus.apps.api.app.services.sysadmin.traffic import TrafficEvent

    event = TrafficEvent(
        at=1.0,
        kind="service",
        subject="abi.svc.document.v1.get",
        service="document",
        method="get",
        caller="api",
        request_bytes=3,
        reply_bytes=5,
        latency_ms=1.2,
        status="ok",
    )
    frames = _stream_frames(_Tap([event, event]))

    assert frames[0] == {"type": "status", "state": "live", "source": "nats", "skipped": {}}
    batches = [f for f in frames if f["type"] == "traffic"]
    assert sum(len(b["events"]) for b in batches) == 2
    assert batches[0]["events"][0]["service"] == "document"
    assert frames[-1]["type"] == "status" and frames[-1]["state"] == "ended"


def test_traffic_stream_explains_an_unavailable_tap():
    frames = _stream_frames(_Tap(unavailable="NATS mode is off"))

    assert frames == [
        {"type": "status", "state": "unavailable", "source": "nats", "reason": "NATS mode is off"}
    ]


def test_traffic_stream_is_superadmin_only():
    response = _client(is_superadmin=False).get("/api/admin/system/traffic/stream")

    assert response.status_code == 403


def test_telemetry_view():
    body = _client().get("/api/admin/system/telemetry").json()

    assert body == {
        "enabled": False,
        "service_name": "",
        "ui_url": None,
        "traces_readable": False,
    }


def test_the_real_traffic_hub_dependency_runs_on_the_event_loop(monkeypatch):
    """FastAPI runs sync dependencies in a worker thread, where there is no event
    loop; the hub is per loop, so its dependency must run on the loop itself."""
    import json
    from types import SimpleNamespace

    from naas_abi.apps.nexus.apps.api.app.services.sysadmin import factory

    engine = SimpleNamespace(configuration=SimpleNamespace(nats=None))
    monkeypatch.setattr(factory, "_hubs", None)
    monkeypatch.setattr("naas_abi.ABIModule.get_instance", lambda: SimpleNamespace(engine=engine))
    client = _client()
    client.app.dependency_overrides.pop(factory.get_traffic_hub, None)

    with client.stream("GET", "/api/admin/system/traffic/stream?max_seconds=1") as response:
        assert response.status_code == 200
        frames = [
            json.loads(line[6:]) for line in response.iter_lines() if line.startswith("data: ")
        ]

    assert frames == [
        {"type": "status", "state": "unavailable", "source": "nats", "reason": "NATS mode is off"}
    ]
