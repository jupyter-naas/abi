"""Run the shared document port contract through an actual NATS server."""

import pytest
from naas_abi_core.engine import nats_runtime
from naas_abi_core.engine.IEngine import IEngine
from naas_abi_core.engine.nats_rpc_integration_test import (  # noqa: F401 - pytest fixture
    SECRET,
    broker,
)
from naas_abi_core.engine.nats_test_tokens import TEST_TOKENS
from naas_abi_core.services.document.adapters.primary.document__primary_adapter__NATS import (
    DocumentPrimaryAdapterNATS,
)
from naas_abi_core.services.document.adapters.secondary.DocumentSecondaryAdapterNATSClient import (
    DocumentSecondaryAdapterNATSClient,
)
from naas_abi_core.services.document.adapters.secondary.DocumentSecondaryAdapterSQLite import (
    DocumentSecondaryAdapterSQLite,
)
from naas_abi_core.services.document.DocumentPort import (
    CollectionNotFound,
    CollectionSpec,
)
from naas_abi_core.services.document.DocumentService import DocumentService
from naas_abi_core.services.document.iam_catalog import CATALOG
from naas_abi_core.services.document.tests.document__secondary_adapter__generic_test import (
    DocumentSecondaryAdapterContract,
)
from naas_abi_core.services.iam.adapters.secondary.IAMStoreMemory import IAMStoreMemory
from naas_abi_core.services.iam.enforcement import internal_call
from naas_abi_core.services.iam.IAMService import IAMService

pytestmark = pytest.mark.integration
BROKER_8_MIB = pytest.mark.parametrize("broker", [8 * 1024 * 1024], indirect=True)


@pytest.fixture
def document_host(broker, tmp_path):  # noqa: F811 - imported pytest fixture
    url, _ = broker
    backend = DocumentSecondaryAdapterSQLite(str(tmp_path / "documents.sqlite"))
    # Not wired into an engine: the adapter contract runs without IAM.
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


@BROKER_8_MIB
class TestDocumentNATS(DocumentSecondaryAdapterContract):
    @pytest.fixture
    def peer(self, document_host):
        client = DocumentSecondaryAdapterNATSClient(
            document_host, TEST_TOKENS.source("peer")
        )
        try:
            yield client
        finally:
            client.close()

    @pytest.fixture
    def adapter(self, document_host):
        client = DocumentSecondaryAdapterNATSClient(
            document_host, TEST_TOKENS.source("test")
        )
        try:
            yield client
        finally:
            client.close()


@BROKER_8_MIB
def test_a_module_reaches_its_own_namespace_only(broker, tmp_path):  # noqa: F811
    """A module's account, once its manifest is approved, reaches its own
    namespace (``${module.id}``), never another module's nor the built-in
    IdP's sealed one."""
    from naas_abi_core.engine.call_context import (
        CallContext,
        Principal,
        use_call_context,
    )
    from naas_abi_core.services.iam.tests.iam_harness import document, statement

    url, _ = broker
    iam = IAMService(IAMStoreMemory())
    iam.bootstrap()
    with internal_call():
        iam.register_catalog(CATALOG)
        account = iam.create_service_account("module/acme/people")
    name = "module/acme/people"
    with use_call_context(
        CallContext(
            principal=Principal(id=account.id, kind="service_account", name=name)
        )
    ):
        iam.submit_manifest(
            "people",
            "acme",
            document(
                statement(
                    "Allow",
                    ["document:*"],
                    [
                        "abi:document:namespace/${module.id}",
                        "abi:document:collection/${module.id}/*",
                        "abi:document:document/${module.id}/*",
                    ],
                )
            ),
        )
    with internal_call():
        iam.approve_manifest(account.id)
    root = DocumentService._for_engine(
        DocumentSecondaryAdapterSQLite(str(tmp_path / "documents.sqlite"))
    )
    root.set_services(IEngine.Services(iam=iam))
    with internal_call():
        for namespace in ("people", "billing"):
            root.for_namespace(namespace).ensure_collection(CollectionSpec(name="c"))
    with internal_call("idp"):
        root.for_namespace("idp").ensure_collection(CollectionSpec(name="users"))
    primary = DocumentPrimaryAdapterNATS(root, SECRET)
    connection = nats_runtime.get_connection(url)
    nats_runtime.run_coro(primary.start(connection))
    module = DocumentSecondaryAdapterNATSClient(
        url, TEST_TOKENS.source(name, subject=account.id)
    )
    try:
        assert module.namespaces() == ["people"]
        assert module.collections("people") == ["c"]
        for other, collection in (("billing", "c"), ("idp", "users")):
            assert module.collections(other) == []
            with pytest.raises(CollectionNotFound):
                module.find(other, collection, [], None, 10, None)
            with pytest.raises(CollectionNotFound):
                module.drop_collection(other, collection)
    finally:
        module.close()
        nats_runtime.run_coro(primary.stop())
        nats_runtime.close()


@pytest.mark.parametrize("broker", [64 * 1024], indirect=True)
def test_find_pages_fit_the_broker_without_overflow(document_host):
    # No overflow host runs here: a reply above 64 KiB would fail outright.
    client = DocumentSecondaryAdapterNATSClient(
        document_host, TEST_TOKENS.source("test")
    )
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
