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
from naas_abi_core.services.document.DocumentPort import CollectionSpec
from naas_abi_core.services.document.DocumentService import DocumentService
from naas_abi_core.services.document.tests.document__secondary_adapter__generic_test import (
    DocumentSecondaryAdapterContract,
)

pytestmark = pytest.mark.integration
BROKER_8_MIB = pytest.mark.parametrize("broker", [8 * 1024 * 1024], indirect=True)


@pytest.fixture
def document_host(broker, tmp_path):  # noqa: F811 - imported pytest fixture
    url, _ = broker
    backend = DocumentSecondaryAdapterSQLite(str(tmp_path / "documents.sqlite"))
    # "test" is the contract's caller; "peer" stays an ordinary identity.
    primary = DocumentPrimaryAdapterNATS(
        DocumentService._for_engine(backend), SECRET, admin_identities={"test"}
    )
    connection = nats_runtime.get_connection(url)
    nats_runtime.run_coro(primary.start(connection))
    nats_runtime.run_coro(connection.flush())
    try:
        yield url
    finally:
        nats_runtime.run_coro(primary.stop())
        nats_runtime.close()
        backend.close()


@BROKER_8_MIB
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


@BROKER_8_MIB
def test_namespaces_need_a_platform_identity(document_host):
    client = DocumentSecondaryAdapterNATSClient(document_host, SECRET, "acme.module")
    try:
        with pytest.raises(PermissionError):
            client.namespaces()
    finally:
        client.close()


@pytest.mark.parametrize("broker", [64 * 1024], indirect=True)
def test_find_pages_fit_the_broker_without_overflow(document_host):
    # No overflow host runs here: a reply above 64 KiB would fail outright.
    client = DocumentSecondaryAdapterNATSClient(document_host, SECRET, "test")
    try:
        client.ensure_collection("module", CollectionSpec(name="records"))
        for n in range(20):
            client.put("module", "records", f"d{n:02d}", {"text": "x" * 10_000}, None)

        ids, cursor, pages = [], None, 0
        while True:
            page = client.find("module", "records", [], None, 100, cursor)
            ids += [doc.id for doc in page.items]
            pages, cursor = pages + 1, page.cursor
            if cursor is None:
                break

        assert ids == [f"d{n:02d}" for n in range(20)]
        assert pages > 1  # cut to a quarter of the broker limit
    finally:
        client.close()
