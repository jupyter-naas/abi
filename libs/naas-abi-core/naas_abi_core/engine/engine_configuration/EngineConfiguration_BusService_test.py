from naas_abi_core.engine.engine_configuration.EngineConfiguration_BusService import (
    BusAdapterConfiguration,
    BusServiceConfiguration,
)
from naas_abi_core.services.bus.BusService import BusService
from naas_abi_core.services.bus.adapters.secondary.PythonQueueAdapter import (
    PythonQueueAdapter,
)


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
