"""The engine's lazily wired cache adapters (EngineConfiguration_CacheService)."""

from types import SimpleNamespace as NS

import pytest
from naas_abi_core.engine.engine_configuration.EngineConfiguration_CacheService import (
    KeyValueBackedAdapter,
    ObjectStorageBackedAdapter,
)
from naas_abi_core.services.cache.tests.cache__secondary_adapter__generic_test import (
    GenericCacheAdapterTest,
)
from naas_abi_core.services.keyvalue.adapters.secondary.PythonAdapter import (
    PythonAdapter,
)
from naas_abi_core.services.keyvalue.KeyValueService import KeyValueService
from naas_abi_core.services.object_storage.adapters.secondary.ObjectStorageSecondaryAdapterFS import (
    ObjectStorageSecondaryAdapterFS,
)
from naas_abi_core.services.object_storage.ObjectStorageService import (
    ObjectStorageService,
)


class TestObjectStorageBackedAdapter(GenericCacheAdapterTest):
    @pytest.fixture
    def adapter(self, tmp_path):
        adapter = ObjectStorageBackedAdapter()
        storage = ObjectStorageService(ObjectStorageSecondaryAdapterFS(str(tmp_path)))
        adapter.wire_services(NS(object_storage=storage))
        return adapter


class TestKeyValueBackedAdapter(GenericCacheAdapterTest):
    @pytest.fixture
    def adapter(self):
        adapter = KeyValueBackedAdapter()
        adapter.wire_services(NS(kv=KeyValueService(PythonAdapter())))
        return adapter


def test_listing_before_wiring_fails_loudly():
    with pytest.raises(RuntimeError, match="not been wired"):
        ObjectStorageBackedAdapter().list_keys()
