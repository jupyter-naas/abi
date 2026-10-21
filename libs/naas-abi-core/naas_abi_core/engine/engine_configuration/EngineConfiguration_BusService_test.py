from naas_abi_core.engine.engine_configuration.EngineConfiguration_BusService import (
    BusAdapterConfiguration,
    BusServiceConfiguration,
)
from naas_abi_core.services.bus.adapters.secondary.NATSJetStreamAdapter import (
    NATSJetStreamAdapter,
)
from naas_abi_core.services.bus.adapters.secondary.PythonQueueAdapter import (
    PythonQueueAdapter,
)
from naas_abi_core.services.bus.BusService import BusService


def test_bus_service_configuration_python_queue(tmp_path):
    configuration = BusServiceConfiguration(
        bus_adapter=BusAdapterConfiguration(
            adapter="python_queue",
            config={"persistence_path": str(tmp_path / "bus.sqlite3")},
        )
    )

    adapter = configuration.bus_adapter.load()
    assert isinstance(adapter, PythonQueueAdapter)
    assert isinstance(configuration.load(), BusService)


def test_bus_service_configuration_nats_jetstream():
    # Construction is lazy (see NATSJetStreamAdapter's test_init_is_lazy),
    # so this doesn't need a live NATS server.
    configuration = BusServiceConfiguration(
        bus_adapter=BusAdapterConfiguration(
            adapter="nats_jetstream",
            config={"nats_url": "nats://127.0.0.1:4222"},
        )
    )

    adapter = configuration.bus_adapter.load()
    assert isinstance(adapter, NATSJetStreamAdapter)
    assert isinstance(configuration.load(), BusService)
