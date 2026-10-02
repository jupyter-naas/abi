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
        jwt_secret="s" * 48,
        nats_url="nats://nats:4222",
        discovery={"project": "zen"},
        monitoring_url="http://nats:8222",
    )
    service = build_sysadmin_service(_engine(nats))

    assert isinstance(service.micro, NatsMicroServiceMonitor)
    assert isinstance(service.registry, DiscoveryModuleRegistry)
    assert isinstance(service.monitor, NatsHttpMonitor)


def test_missing_discovery_or_monitoring_url_is_named():
    service = build_sysadmin_service(_engine(NATSConfiguration(jwt_secret="s" * 48)))

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

    nats = NATSConfiguration(jwt_secret="s" * 48)
    engine = _engine(nats)
    engine.configuration.telemetry = TelemetryConfiguration(
        enabled=True, query_url="http://jaeger:16686", ui_url="http://localhost:16686"
    )
    tap = build_traffic_hub(engine)._tap_factory()
    assert [type(f()) for f in tap._factories] == [JaegerSpanTap, NatsTrafficTap]
    assert tap._factories[0]()._url == "http://jaeger:16686"

    without_tracing = build_traffic_hub(_engine(nats))._tap_factory()
    assert [type(f()) for f in without_tracing._factories] == [NatsTrafficTap]
