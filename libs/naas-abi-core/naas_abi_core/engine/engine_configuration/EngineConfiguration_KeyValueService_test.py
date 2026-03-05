from naas_abi_core.engine.engine_configuration.EngineConfiguration_KeyValueService import (
    KeyValueAdapterConfiguration,
    KeyValueServiceConfiguration,
)
from naas_abi_core.services.keyvalue.KeyValueService import KeyValueService
from naas_abi_core.services.keyvalue.adapters.secondary.PythonAdapter import (
    PythonAdapter,
)


def test_keyvalue_service_configuration_python_adapter(tmp_path):
    configuration = KeyValueServiceConfiguration(
        kv_adapter=KeyValueAdapterConfiguration(
            adapter="python",
            config={"persistence_path": str(tmp_path / "kv.sqlite3")},
        )
    )

    adapter = configuration.kv_adapter.load()
    assert isinstance(adapter, PythonAdapter)
    assert isinstance(configuration.load(), KeyValueService)
