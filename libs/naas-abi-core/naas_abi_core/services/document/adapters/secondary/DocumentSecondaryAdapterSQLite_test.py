import pytest
from naas_abi_core.services.document.adapters.secondary.DocumentSecondaryAdapterSQLite import (
    DocumentSecondaryAdapterSQLite,
)
from naas_abi_core.services.document.tests.document__secondary_adapter__generic_test import (
    DocumentSecondaryAdapterContract,
)


class TestDocumentSecondaryAdapterSQLite(DocumentSecondaryAdapterContract):
    @pytest.fixture
    def peer(self, tmp_path, adapter):
        peer = DocumentSecondaryAdapterSQLite(str(tmp_path / "documents.sqlite"))
        yield peer
        peer.close()

    @pytest.fixture
    def adapter(self, tmp_path):
        adapter = DocumentSecondaryAdapterSQLite(str(tmp_path / "documents.sqlite"))
        yield adapter
        adapter.close()
