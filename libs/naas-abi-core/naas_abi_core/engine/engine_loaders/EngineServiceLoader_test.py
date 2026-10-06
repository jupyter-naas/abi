from unittest.mock import MagicMock

from naas_abi_core.engine.engine_configuration.EngineConfiguration import (
    EngineConfiguration,
)
from naas_abi_core.engine.engine_loaders.EngineNATSDependencies import (
    EngineNATSDependencies,
)
from naas_abi_core.engine.engine_loaders.EngineServiceLoader import EngineServiceLoader
from naas_abi_core.engine.IEngine import IEngine
from naas_abi_core.module.Module import ModuleDependencies
from naas_abi_core.services.bus.BusService import BusService
from naas_abi_core.services.document.DocumentService import DocumentService

# IEngine.Services accessor -> services configuration field, for every service
# loaded on demand (model_registry/coding_environment/source_control always load).
ON_DEMAND = {
    "document": "document",
    "object_storage": "object_storage",
    "dataset": "dataset",
    "triple_store": "triple_store",
    "vector_store": "vector_store",
    "secret": "secret",
    "kv": "kv",
    "email": "email",
    "cache": "cache",
    "activity_log": "activity_log",
    "events": "event",
}


def _loader(monkeypatch, nats):
    """A loader whose service owners are stubs, so no backend is touched."""
    config = EngineConfiguration(
        api={}, global_config={"ai_mode": "local"}, modules=[], nats=nats, services={}
    )
    for field in ON_DEMAND.values():
        owner_config = getattr(config.services, field)
        monkeypatch.setattr(type(owner_config), "load", lambda self: MagicMock())
    monkeypatch.setattr(EngineServiceLoader, "_load_bus", lambda self: MagicMock())
    return EngineServiceLoader(config)


def _available(services: IEngine.Services) -> set[str]:
    return {
        name for name in [*ON_DEMAND, "bus"] if getattr(services, f"{name}_available")()
    }


def test_nats_mode_loads_every_service_without_module_dependencies(monkeypatch):
    # In NATS mode the engine is the service host for remote modules too, which
    # declare their dependencies at runtime, not in this engine's module list.
    services = _loader(monkeypatch, {"jwt_secret": "test"}).load_services({})

    assert _available(services) == {*ON_DEMAND, "bus"}


def test_without_nats_only_declared_services_load(monkeypatch):
    services = _loader(monkeypatch, None).load_services(
        {"m": ModuleDependencies(modules=[], services=[DocumentService])}
    )

    assert _available(services) == {"document"}


def test_bus_telemetry_setting_survives_owner_and_dependency_wiring(monkeypatch):
    config = EngineConfiguration(
        api={},
        global_config={"ai_mode": "local"},
        modules=[],
        nats={"jwt_secret": "test"},
        services={
            "bus": {
                "emit_message_events": True,
                "bus_adapter": {"adapter": "nats_jetstream", "config": {}},
            }
        },
    )
    adapter = MagicMock()
    monkeypatch.setattr(
        "naas_abi_core.services.bus.adapters.secondary.NATSJetStreamAdapter.NATSJetStreamAdapter",
        lambda *args: adapter,
    )
    bus = EngineServiceLoader(config)._load_bus()
    assert bus.emit_message_events
    wiring = EngineNATSDependencies(config.nats)
    try:
        dependencies = wiring.build(
            IEngine.Services(bus=BusService(MagicMock(), emit_message_events=True))
        )
        assert dependencies.bus.emit_message_events
        assert dependencies.bus.services_wired
    finally:
        wiring.close()


def _config(nats, services=None):
    return EngineConfiguration(
        api={},
        global_config={"ai_mode": "local"},
        modules=[],
        nats=nats,
        services=services or {},
    )


def test_local_backends_cover_every_service_a_nats_engine_owns():
    loader = EngineServiceLoader(_config({"jwt_secret": "test"}))

    found = loader.local_backends({})

    # Defaults keep data on this host; the bus is the broker's JetStream.
    assert {
        "activity_log",
        "cache",
        "coding_environment",
        "dataset",
        "document",
        "event",
        "kv",
        "object_storage",
        "source_control",
        "triple_store",
        "vector_store",
    } == set(found)


def test_local_backends_skip_services_this_engine_does_not_load():
    loader = EngineServiceLoader(_config(None))

    found = loader.local_backends(
        {"m": ModuleDependencies(modules=[], services=[DocumentService])}
    )

    # Coding environment and source control always load.
    assert set(found) == {"document", "coding_environment", "source_control"}


def test_an_activity_log_in_documents_loads_the_document_service(monkeypatch):
    from naas_abi_core.services.activity_log.ActivityLogService import (
        ActivityLogService,
    )

    services = _loader(monkeypatch, None).load_services(
        {"m": ModuleDependencies(modules=[], services=[ActivityLogService])}
    )

    assert services.document_available()
    assert services.activity_log_available()
