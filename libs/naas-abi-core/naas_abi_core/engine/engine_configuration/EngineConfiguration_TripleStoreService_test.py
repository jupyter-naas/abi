from naas_abi_core.engine.engine_configuration.EngineConfiguration_TripleStoreService import (
    ApacheJenaTDB2AdapterConfiguration,
    AWSNeptuneSSHTunnelAdapterConfiguration,
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


def test_triple_store_service_configuration_aws_neptune_sshtunnel():
    import os

    from dotenv import load_dotenv

    load_dotenv()

    from naas_abi_core.services.triple_store.adaptors.secondary.AWSNeptune import (
        AWSNeptuneSSHTunnel,
    )

    configuration = TripleStoreServiceConfiguration(
        triple_store_adapter=TripleStoreAdapterConfiguration(
            adapter="aws_neptune_sshtunnel",
            config=AWSNeptuneSSHTunnelAdapterConfiguration(
                aws_region_name=os.environ.get("AWS_REGION"),
                aws_access_key_id=os.environ.get("AWS_ACCESS_KEY_ID"),
                aws_secret_access_key=os.environ.get("AWS_SECRET_ACCESS_KEY"),
                db_instance_identifier=os.environ.get(
                    "AWS_NEPTUNE_DB_INSTANCE_IDENTIFIER"
                ),
                bastion_host=os.environ.get("AWS_BASTION_HOST"),
                bastion_port=int(os.environ.get("AWS_BASTION_PORT")),
                bastion_user=os.environ.get("AWS_BASTION_USER"),
                bastion_private_key=os.environ.get("AWS_BASTION_PRIVATE_KEY"),
            ),
        ),
    )

    assert configuration.triple_store_adapter is not None

    triple_store_adapter = configuration.triple_store_adapter.load()

    assert triple_store_adapter is not None
    assert isinstance(triple_store_adapter, ITripleStorePort)
    assert isinstance(triple_store_adapter, AWSNeptuneSSHTunnel)

    triple_store_service = configuration.load()

    assert triple_store_service is not None
    assert isinstance(triple_store_service, TripleStoreService)


def test_triple_store_service_configuration_apache_jena_tdb2():
    from unittest.mock import Mock, patch

    from naas_abi_core.services.triple_store.adaptors.secondary.ApacheJenaTDB2 import (
        ApacheJenaTDB2,
    )

    with (
        patch(
            "naas_abi_core.services.triple_store.adaptors.secondary.ApacheJenaTDB2.requests.get"
        ) as mock_get,
        patch(
            "naas_abi_core.services.triple_store.adaptors.secondary.ApacheJenaTDB2.requests.post"
        ) as mock_post,
    ):
        mock_get.return_value = Mock(status_code=200)
        mock_get.return_value.raise_for_status = Mock()
        mock_post.return_value = Mock(status_code=200)
        mock_post.return_value.raise_for_status = Mock()

        configuration = TripleStoreServiceConfiguration(
            triple_store_adapter=TripleStoreAdapterConfiguration(
                adapter="apache_jena_tdb2",
                config=ApacheJenaTDB2AdapterConfiguration(
                    jena_tdb2_url="http://localhost:3030/ds",
                    timeout=120,
                ),
            )
        )

        assert configuration.triple_store_adapter is not None

        triple_store_adapter = configuration.triple_store_adapter.load()

        assert triple_store_adapter is not None
        assert isinstance(triple_store_adapter, ITripleStorePort)
        assert isinstance(triple_store_adapter, ApacheJenaTDB2)

        triple_store_service = configuration.load()

        assert triple_store_service is not None
        assert isinstance(triple_store_service, TripleStoreService)
