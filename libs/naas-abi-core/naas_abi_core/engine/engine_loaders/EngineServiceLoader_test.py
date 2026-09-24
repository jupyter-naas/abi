from unittest.mock import MagicMock

from naas_abi_core.engine.engine_configuration.EngineConfiguration import (
    EngineConfiguration,
)
from naas_abi_core.engine.engine_loaders.EngineNATSDependencies import (
    EngineNATSDependencies,
)
from naas_abi_core.engine.engine_loaders.EngineServiceLoader import EngineServiceLoader
from naas_abi_core.engine.IEngine import IEngine
from naas_abi_core.services.bus.BusService import BusService


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
