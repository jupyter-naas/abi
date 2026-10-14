import asyncio

import pytest
from naas_abi.apps.nexus.apps.api.app.services.sysadmin.adapters.secondary.in_memory import (
    InMemoryEngineModules,
    InMemoryMicroServiceMonitor,
    InMemoryModuleRegistry,
    InMemoryNatsServerMonitor,
    InMemoryServiceConfiguration,
    UnavailableSource,
)
from naas_abi.apps.nexus.apps.api.app.services.sysadmin.port import SourceUnavailable
from naas_abi.apps.nexus.apps.api.app.services.sysadmin.service import SysAdminService
from naas_abi.apps.nexus.apps.api.app.services.sysadmin.tests import fixtures


def _service(**overrides):
    parts = {
        "configuration": InMemoryServiceConfiguration(fixtures.configured_services()),
        "engine_modules": InMemoryEngineModules(fixtures.engine_modules()),
        "micro": InMemoryMicroServiceMonitor(fixtures.micro_instances()),
        "registry": InMemoryModuleRegistry(fixtures.remote_instances()),
        "monitor": InMemoryNatsServerMonitor(
            fixtures.nats_server(), fixtures.nats_connections(), fixtures.jetstream()
        ),
    }
    parts.update(overrides)
    return SysAdminService(**parts)


def test_kernel_services_merge_configuration_with_live_instances():
    view = asyncio.run(_service().kernel_services())
    services = {s.name: s for s in view.services}

    assert services["document"].adapters == ("postgresql",)
    assert services["document"].status == "serving" and len(services["document"].instances) == 2
    assert services["kv"].nats_service == "keyvalue" and services["kv"].status == "serving"
    assert services["secret"].status == "silent"  # configured, exposed, nobody answering
    assert services["bus"].status == "not_exposed"  # JetStream, not a micro service
    assert view.sources["nats"].available


def test_micro_services_nobody_configured_still_show_up():
    from naas_abi.apps.nexus.apps.api.app.services.sysadmin.port import MicroServiceInstance

    micro = InMemoryMicroServiceMonitor(
        [*fixtures.micro_instances(), MicroServiceInstance("custom", "c1", "1", "", ())]
    )
    services = {s.name: s for s in asyncio.run(_service(micro=micro).kernel_services()).services}

    assert services["custom"].adapters == () and services["custom"].status == "serving"


def test_without_nats_services_are_listed_from_configuration_only():
    view = asyncio.run(
        _service(micro=UnavailableSource("nats", "NATS mode is off")).kernel_services()
    )

    assert not view.sources["nats"].available
    assert view.sources["nats"].reason == "NATS mode is off"
    assert all(s.instances == () for s in view.services)


def test_modules_list_engine_and_remote_and_survive_a_registry_outage():
    view = asyncio.run(_service().modules())
    assert [m.module_id for m in view.engine] == ["acme.jobs", "acme.quiet"]
    assert {m.module_id for m in view.remote} == {"ops.researcher", "ops.orchestrator"}

    down = asyncio.run(_service(registry=UnavailableSource("discovery", "no responders")).modules())
    assert len(down.engine) == 2 and down.remote == ()
    assert down.sources["discovery"].reason == "no responders"


def test_overview_counts_everything_and_reports_each_source():
    overview = asyncio.run(_service().overview())

    assert overview.kernel_services == 5
    assert overview.serving_services == 2  # document, kv
    assert overview.service_instances == 3
    assert overview.requests == 5
    assert overview.engine_modules == 2
    assert overview.remote_modules == {"READY": 1, "STARTING": 1}
    assert overview.server.version == "2.14.7"
    assert (
        overview.jetstream_streams,
        overview.jetstream_consumers,
        overview.jetstream_messages,
    ) == (2, 1, 5)
    assert all(s.available for s in overview.sources.values())


def test_overview_degrades_per_source():
    down = UnavailableSource("nats_monitor", "connection refused")
    overview = asyncio.run(_service(monitor=down).overview())

    assert overview.server is None and overview.jetstream_streams == 0
    assert overview.sources["nats_monitor"].reason == "connection refused"
    assert overview.sources["nats"].available


def test_nats_views_raise_when_their_source_is_down():
    service = _service(monitor=UnavailableSource("nats_monitor", "connection refused"))

    with pytest.raises(SourceUnavailable):
        asyncio.run(service.nats_server())


def test_telemetry_is_reported_as_configured():
    from naas_abi.apps.nexus.apps.api.app.services.sysadmin.port import TelemetryInfo

    info = TelemetryInfo(enabled=True, service_name="zen-engine", ui_url="http://localhost:16686")
    service = _service(telemetry=info)

    assert asyncio.run(service.overview()).telemetry == info
    assert service.telemetry == info
    assert _service().telemetry == TelemetryInfo(enabled=False, service_name="", ui_url=None)
