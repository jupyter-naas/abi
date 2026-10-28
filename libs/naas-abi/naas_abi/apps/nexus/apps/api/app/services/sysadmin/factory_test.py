import asyncio
from types import SimpleNamespace as NS

import pytest
from naas_abi.apps.nexus.apps.api.app.services.sysadmin.adapters.secondary.discovery_registry import (
    DiscoveryModuleRegistry,
)
from naas_abi.apps.nexus.apps.api.app.services.sysadmin.adapters.secondary.nats_http_monitor import (
    NatsHttpMonitor,
)
from naas_abi.apps.nexus.apps.api.app.services.sysadmin.adapters.secondary.nats_micro import (
    NatsMicroServiceMonitor,
)
from naas_abi.apps.nexus.apps.api.app.services.sysadmin.factory import build_sysadmin_service
from naas_abi.apps.nexus.apps.api.app.services.sysadmin.port import SourceUnavailable
from naas_abi_core.engine.engine_configuration.EngineConfiguration import (
    NATSConfiguration,
    ServicesConfiguration,
)


def _engine(nats):
    return NS(
        configuration=NS(services=ServicesConfiguration(), nats=nats),
        modules={
            "acme.jobs": NS(
                name="Acme", description="", agents=[], orchestrations=[], ontologies=[]
            )
        },
    )


def test_without_nats_every_nats_source_explains_why():
    service = build_sysadmin_service(_engine(None))
    overview = asyncio.run(service.overview())

    assert overview.engine_modules == 1 and overview.kernel_services > 10
    for source in ("nats", "discovery", "nats_monitor"):
        assert overview.sources[source].reason == "NATS mode is off"


def test_nats_mode_wires_the_real_adapters():
    nats = NATSConfiguration(
        nats_url="nats://nats:4222",
        discovery={"project": "zen"},
        monitoring_url="http://nats:8222",
    )
    service = build_sysadmin_service(_engine(nats))

    assert isinstance(service.micro, NatsMicroServiceMonitor)
    assert isinstance(service.registry, DiscoveryModuleRegistry)
    assert isinstance(service.monitor, NatsHttpMonitor)


def test_missing_discovery_or_monitoring_url_is_named():
    service = build_sysadmin_service(_engine(NATSConfiguration()))

    assert "nats.discovery" in asyncio.run(service.modules()).sources["discovery"].reason
    with pytest.raises(SourceUnavailable, match="nats.monitoring_url"):
        asyncio.run(service.nats_server())


def test_telemetry_comes_from_the_engine_configuration():
    from naas_abi_core.engine.engine_configuration.EngineConfiguration import (
        TelemetryConfiguration,
    )

    engine = _engine(None)
    engine.configuration.telemetry = TelemetryConfiguration(
        enabled=True, service_name="zen-engine", ui_url="http://localhost:16686"
    )
    info = build_sysadmin_service(engine).telemetry

    assert (info.enabled, info.service_name, info.ui_url) == (
        True,
        "zen-engine",
        "http://localhost:16686",
    )
    assert build_sysadmin_service(_engine(None)).telemetry.enabled is False


@pytest.mark.parametrize(
    ("urls", "readable"),
    [
        ({"query_url": "http://jaeger:16686"}, True),
        ({"ui_url": "http://localhost:16686"}, True),
        ({}, False),
    ],
)
def test_telemetry_says_whether_the_traces_tab_can_read_traces(urls, readable):
    # Live traffic links trace ids to the Traces tab, which reads them through
    # query_url (else ui_url): ui_url alone must not decide it.
    from naas_abi_core.engine.engine_configuration.EngineConfiguration import (
        TelemetryConfiguration,
    )

    engine = _engine(None)
    engine.configuration.telemetry = TelemetryConfiguration(enabled=True, **urls)

    assert build_sysadmin_service(engine).telemetry.traces_readable is readable
    assert build_sysadmin_service(_engine(None)).telemetry.traces_readable is False


def test_live_traffic_prefers_traces_and_falls_back_to_nats():
    from naas_abi.apps.nexus.apps.api.app.services.sysadmin.adapters.secondary.jaeger_traffic_tap import (
        JaegerSpanTap,
    )
    from naas_abi.apps.nexus.apps.api.app.services.sysadmin.adapters.secondary.nats_traffic_tap import (
        NatsTrafficTap,
    )
    from naas_abi.apps.nexus.apps.api.app.services.sysadmin.factory import build_traffic_hub
    from naas_abi_core.engine.engine_configuration.EngineConfiguration import (
        TelemetryConfiguration,
    )

    nats = NATSConfiguration()
    engine = _engine(nats)
    engine.configuration.telemetry = TelemetryConfiguration(
        enabled=True, query_url="http://jaeger:16686", ui_url="http://localhost:16686"
    )
    tap = build_traffic_hub(engine)._tap_factory()
    assert [type(f()) for f in tap._factories] == [JaegerSpanTap, NatsTrafficTap]
    assert tap._factories[0]()._url == "http://jaeger:16686"

    without_tracing = build_traffic_hub(_engine(nats))._tap_factory()
    assert [type(f()) for f in without_tracing._factories] == [NatsTrafficTap]


def test_the_trace_store_reads_jaeger_when_tracing_is_configured():
    from naas_abi.apps.nexus.apps.api.app.services.sysadmin.adapters.secondary.jaeger_trace_store import (
        JaegerTraceStore,
    )
    from naas_abi.apps.nexus.apps.api.app.services.sysadmin.factory import build_trace_store
    from naas_abi_core.engine.engine_configuration.EngineConfiguration import (
        TelemetryConfiguration,
    )

    def configuration(**telemetry):
        return NS(telemetry=TelemetryConfiguration(**telemetry) if telemetry else None)

    store = build_trace_store(
        configuration(
            enabled=True, query_url="http://jaeger:16686", ui_url="http://localhost:16686"
        )
    )
    assert isinstance(store, JaegerTraceStore) and store._url == "http://jaeger:16686"
    only_ui = build_trace_store(configuration(enabled=True, ui_url="http://localhost:16686"))
    assert isinstance(only_ui, JaegerTraceStore) and only_ui._url == "http://localhost:16686"
    for off in (configuration(), configuration(enabled=False, query_url="http://jaeger:16686")):
        unavailable = build_trace_store(off)
        assert isinstance(unavailable, SourceUnavailable)
        assert (unavailable.source, unavailable.reason) == (
            "tracing",
            "telemetry is not enabled (telemetry.query_url)",
        )


class _Services:
    """An EngineProxy-like view: secret is not a dependency of the module."""

    def __init__(self, storage):
        self.object_storage = storage

    @property
    def secret(self):
        raise ValueError("Module naas_abi does not have access to Secret")


def test_resource_admin_wires_real_adapters_and_names_missing_services(tmp_path):
    from naas_abi.apps.nexus.apps.api.app.services.sysadmin.adapters.secondary.object_storage_resources import (
        ObjectStorageResources,
    )
    from naas_abi.apps.nexus.apps.api.app.services.sysadmin.factory import build_resource_admin
    from naas_abi_core.services.object_storage.adapters.secondary.ObjectStorageSecondaryAdapterFS import (
        ObjectStorageSecondaryAdapterFS,
    )
    from naas_abi_core.services.object_storage.ObjectStorageService import ObjectStorageService

    storage = ObjectStorageService(ObjectStorageSecondaryAdapterFS(str(tmp_path)))
    storage.put_object("docs", "a.txt", b"hi")

    engine = NS(services=_Services(storage), configuration=NS(nats=None))
    admin = build_resource_admin(engine, audit_engine=lambda: None)
    services = {s.name: s for s in admin.services()}

    assert isinstance(admin._source("object_storage"), ObjectStorageResources)
    assert services["object_storage"].available is True
    assert services["secret"].available is False
    assert "does not have access to Secret" in services["secret"].reason
    assert services["bus"].reason == services["discovery"].reason == "NATS mode is off"
    # Every kernel service is listed, available or with the reason it is not.
    assert {"dataset", "document", "triple_store", "vector_store"} <= set(services)
    page = asyncio.run(admin.list("object_storage"))
    assert [e.id for e in page.entries] == ["docs"]


def test_jobs_without_nats_list_engine_jobs_and_name_what_is_off():
    from naas_abi.apps.nexus.apps.api.app.services.sysadmin.factory import build_jobs_admin
    from naas_abi_sdk.jobs import Cron, JobDescriptor

    module = NS(jobs=(JobDescriptor("nightly", triggers=(Cron("0 0 6 * * *", time_zone="UTC"),)),))
    engine = NS(
        modules={"acme.jobs": module},
        configuration=NS(nats=None, telemetry=None),
        services=NS(dataset_available=lambda: False),
    )

    overview = asyncio.run(build_jobs_admin(engine, audit_engine=lambda: None).overview())

    assert [j.definition.key for j in overview.jobs] == ["acme.jobs/nightly"]
    assert overview.project == "default"
    assert overview.sources["engine"].available
    for source in ("discovery", "runs", "queue"):
        assert overview.sources[source].available is False
    assert "NATS mode is off" in overview.sources["runs"].reason


def test_job_owners_include_kernel_dataset_jobs_in_nats_mode():
    from naas_abi.apps.nexus.apps.api.app.services.sysadmin.factory import job_owners

    nats = NS(discovery=None)
    engine = NS(
        modules={"acme.jobs": NS(jobs=())},
        configuration=NS(nats=nats),
        services=NS(dataset_available=lambda: True),
    )

    owners = job_owners(engine)

    assert "naas_abi_core.dataset" in owners
    assert {j.name for j in owners["naas_abi_core.dataset"].jobs} == {
        "dataset_compaction",
        "dataset_cleanup",
        "dataset_catalog_monitor",
    }
    no_nats = NS(
        modules={}, configuration=NS(nats=None), services=NS(dataset_available=lambda: True)
    )
    assert "naas_abi_core.dataset" not in job_owners(no_nats)


def test_job_owners_are_the_engine_s_when_the_platform_proxy_lists_them():
    """Agent memory and the jobs service adapters offer (activity log copy, event
    archive) appear in the Jobs tab, so an admin can run them."""
    from naas_abi.apps.nexus.apps.api.app.services.sysadmin.factory import job_owners

    kernel = {
        "acme.jobs": NS(jobs=()),
        "naas_abi_core.agent_memory": NS(jobs=()),
        "naas_abi_core.activity_log": NS(jobs=()),
    }
    engine = NS(
        modules={"acme.jobs": kernel["acme.jobs"]},
        configuration=NS(nats=NS(discovery=None)),
        services=NS(dataset_available=lambda: False),
        job_owners=lambda: dict(kernel),
    )

    owners = job_owners(engine)

    assert {k: owners[k] for k in kernel} == kernel


def test_agents_without_nats_name_what_is_off():
    from naas_abi.apps.nexus.apps.api.app.services.sysadmin.factory import build_agents_admin
    from naas_abi.apps.nexus.apps.api.app.services.sysadmin.port import SourceUnavailable

    engine = NS(modules={}, configuration=NS(nats=None, telemetry=None), services=NS())
    admin = build_agents_admin(engine, audit_engine=lambda: None)

    with pytest.raises(SourceUnavailable, match="NATS mode is off") as raised:
        asyncio.run(admin.runs(module="acme.agents"))
    assert raised.value.source == "agent_runs"
    with pytest.raises(SourceUnavailable) as raised:
        asyncio.run(admin.modules())
    assert raised.value.source == "discovery"


def test_agents_in_nats_mode_read_the_engine_documents_and_discovery():
    from naas_abi.apps.nexus.apps.api.app.services.sysadmin.adapters.secondary.document_agent_runs import (
        DocumentAgentRunStore,
    )
    from naas_abi.apps.nexus.apps.api.app.services.sysadmin.adapters.secondary.nats_agent_control import (
        NatsAgentControl,
    )
    from naas_abi.apps.nexus.apps.api.app.services.sysadmin.factory import build_agents_admin
    from naas_abi_sdk.agent_host import agent_runs_collection

    nats = NS(
        nats_url="nats://localhost:4222",
        discovery=NS(project="zen"),
        monitoring_url=None,
    )
    engine = NS(modules={}, configuration=NS(nats=nats, telemetry=None), services=NS())

    admin = build_agents_admin(engine, audit_engine=lambda: None)

    assert isinstance(admin._runs, DocumentAgentRunStore)
    assert admin._runs.runs_collection == agent_runs_collection("zen")
    assert isinstance(admin._control, NatsAgentControl) and admin._control.project == "zen"


def test_workflows_are_wired_over_the_jobs_adapters_in_nats_mode(tmp_path):
    """An engine module's workflow is listed with its schema, and a run read through
    the factory's adapters has its steps (document root: ``engine.services.document_admin``)."""
    from naas_abi.apps.nexus.apps.api.app.services.sysadmin.adapters.secondary.json_schema_validator import (
        JsonSchemaValidator,
    )
    from naas_abi.apps.nexus.apps.api.app.services.sysadmin.factory import build_jobs_admin
    from naas_abi.apps.nexus.apps.api.app.services.workflows.service import WorkflowsService
    from naas_abi_core.services.document.adapters.secondary.DocumentSecondaryAdapterSQLite import (
        DocumentSecondaryAdapterSQLite,
    )
    from naas_abi_core.services.document.DocumentPort import CollectionSpec, FieldSpec
    from naas_abi_core.services.document.DocumentService import DocumentService
    from naas_abi_sdk.jobs import JobDescriptor, runs_collection
    from naas_abi_sdk.workflows import steps_collection

    documents = DocumentService._for_engine(
        DocumentSecondaryAdapterSQLite(str(tmp_path / "documents.sqlite"))
    )
    view = documents.for_namespace("acme.flows")
    view.ensure_collection(CollectionSpec(name=runs_collection("zen")))
    view.ensure_collection(
        CollectionSpec(
            name=steps_collection("zen"),
            fields=(FieldSpec(name="run_id", type="string", indexed=True),),
        )
    )
    view.put(
        runs_collection("zen"),
        "ingest:1",
        {"job": "ingest", "status": "SUCCEEDED", "result": {"count": 1}, "fired_at": "t0"},
    )
    view.put(
        steps_collection("zen"),
        "ingest:1#fetch",
        {
            "run_id": "ingest:1",
            "key": "fetch",
            "kind": "step",
            "status": "SUCCEEDED",
            "fired_at": "t0",
        },
    )
    schema = '{"type": "object", "properties": {"n": {"type": "integer"}}, "required": ["n"]}'
    module = NS(jobs=(JobDescriptor("ingest", kind="workflow", input_schema=schema),))
    engine = NS(
        modules={"acme.flows": module},
        configuration=NS(
            nats=NS(discovery=NS(project="zen"), nats_url="nats://127.0.0.1:1"),
            telemetry=None,
        ),
        services=NS(dataset_available=lambda: False, document_admin=documents),
    )
    admin = build_jobs_admin(engine, audit_engine=lambda: None)
    service = WorkflowsService(admin)

    listed = asyncio.run(service.list()).workflows
    view_ = asyncio.run(service.status("acme.flows", "ingest:1"))

    assert [(w.key, w.input_schema["required"]) for w in listed] == [("acme.flows/ingest", ["n"])]
    assert isinstance(admin._validator, JsonSchemaValidator)
    assert (view_.run.status, view_.run.result) == ("SUCCEEDED", {"count": 1})
    assert [s.key for s in view_.workflow.steps] == ["fetch"]


def test_workflows_without_nats_are_listed_but_have_no_runs_to_read():
    from naas_abi.apps.nexus.apps.api.app.services.sysadmin.factory import build_jobs_admin
    from naas_abi.apps.nexus.apps.api.app.services.workflows.service import WorkflowsService
    from naas_abi_sdk.jobs import JobDescriptor

    module = NS(jobs=(JobDescriptor("ingest", kind="workflow"),))
    engine = NS(
        modules={"acme.flows": module},
        configuration=NS(nats=None, telemetry=None),
        services=NS(dataset_available=lambda: False),
    )
    service = WorkflowsService(build_jobs_admin(engine, audit_engine=lambda: None))

    assert [w.key for w in asyncio.run(service.list()).workflows] == ["acme.flows/ingest"]
    with pytest.raises(SourceUnavailable) as exc:
        asyncio.run(service.status("acme.flows", "ingest:1"))
    assert exc.value.source == "runs"
