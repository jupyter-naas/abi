"""Run the shared document port contract through an actual NATS server."""

import pytest
from naas_abi_core.engine import nats_runtime
from naas_abi_core.engine.nats_rpc_integration_test import (  # noqa: F401 - pytest fixture
    SECRET,
    broker,
)
from naas_abi_core.services.document.adapters.primary.document__primary_adapter__NATS import (
    DocumentPrimaryAdapterNATS,
)
from naas_abi_core.services.document.adapters.secondary.DocumentSecondaryAdapterNATSClient import (
    DocumentSecondaryAdapterNATSClient,
)
from naas_abi_core.services.document.adapters.secondary.DocumentSecondaryAdapterSQLite import (
    DocumentSecondaryAdapterSQLite,
)
from naas_abi_core.services.document.DocumentService import DocumentService
from naas_abi_core.services.document.tests.document__secondary_adapter__generic_test import (
    DocumentSecondaryAdapterContract,
)

pytestmark = [
    pytest.mark.integration,
    pytest.mark.parametrize("broker", [8 * 1024 * 1024], indirect=True),
]


@pytest.fixture
def document_host(broker, tmp_path):  # noqa: F811 - imported pytest fixture
    url, _ = broker
    backend = DocumentSecondaryAdapterSQLite(str(tmp_path / "documents.sqlite"))
    primary = DocumentPrimaryAdapterNATS(DocumentService._for_engine(backend), SECRET)
    connection = nats_runtime.get_connection(url)
    nats_runtime.run_coro(primary.start(connection))
    nats_runtime.run_coro(connection.flush())
    try:
        yield url
    finally:
        nats_runtime.run_coro(primary.stop())
        nats_runtime.close()
        backend.close()


class TestDocumentNATS(DocumentSecondaryAdapterContract):
    @pytest.fixture
    def peer(self, document_host):
        client = DocumentSecondaryAdapterNATSClient(document_host, SECRET, "peer")
        try:
            yield client
        finally:
            client.close()

    @pytest.fixture
    def adapter(self, document_host):
        client = DocumentSecondaryAdapterNATSClient(document_host, SECRET, "test")
        try:
            yield client
        finally:
            client.close()
