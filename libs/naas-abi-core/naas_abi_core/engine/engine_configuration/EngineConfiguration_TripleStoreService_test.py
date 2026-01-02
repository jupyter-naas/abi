from naas_abi_core.engine.engine_configuration.EngineConfiguration_TripleStoreService import (
    OxigraphAdapterConfiguration,
    TripleStoreAdapterConfiguration,
    TripleStoreAdapterFilesystemConfiguration,
    TripleStoreServiceConfiguration,
)
from naas_abi_core.services.triple_store.TripleStorePorts import ITripleStorePort
from naas_abi_core.services.triple_store.TripleStoreService import TripleStoreService


def test_triple_store_service_configuration():
    from naas_abi_core.services.triple_store.adaptors.secondary.TripleStoreService__SecondaryAdaptor__Filesystem import (
        TripleStoreService__SecondaryAdaptor__Filesystem,
    )

    configuration = TripleStoreServiceConfiguration(
        triple_store_adapter=TripleStoreAdapterConfiguration(
            adapter="fs",
            config=TripleStoreAdapterFilesystemConfiguration(
                store_path="storage/triplestore/test", triples_path="triples"
            ),
        )
    )
    assert configuration.triple_store_adapter is not None

    triple_store_adapter = configuration.triple_store_adapter.load()

    assert triple_store_adapter is not None
    assert isinstance(triple_store_adapter, ITripleStorePort)
    assert isinstance(
        triple_store_adapter, TripleStoreService__SecondaryAdaptor__Filesystem
    )

    triple_store_service = configuration.load()

    assert triple_store_service is not None
    assert isinstance(triple_store_service, TripleStoreService)


def test_triple_store_service_configuration_naas():
    from naas_abi_core.services.triple_store.adaptors.secondary.Oxigraph import (
        Oxigraph,
    )

    configuration = TripleStoreServiceConfiguration(
        triple_store_adapter=TripleStoreAdapterConfiguration(
            adapter="oxigraph",
            config=OxigraphAdapterConfiguration(
                oxigraph_url="http://localhost:7878",
                timeout=120,
            ),
        )
    )
    assert configuration.triple_store_adapter is not None

    triple_store_adapter = configuration.triple_store_adapter.load()

    assert triple_store_adapter is not None
    assert isinstance(triple_store_adapter, ITripleStorePort)
    assert isinstance(triple_store_adapter, Oxigraph)

    triple_store_service = configuration.load()

    assert triple_store_service is not None
    assert isinstance(triple_store_service, TripleStoreService)
