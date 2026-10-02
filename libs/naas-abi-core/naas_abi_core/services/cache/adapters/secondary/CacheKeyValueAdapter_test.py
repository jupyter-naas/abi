import pytest
from naas_abi_core.services.cache.adapters.secondary.CacheKeyValueAdapter import (
    CacheKeyValueAdapter,
)
from naas_abi_core.services.cache.CachePort import (
    CachedData,
    CacheNotFoundError,
    DataType,
)
from naas_abi_core.services.keyvalue.adapters.secondary.PythonAdapter import (
    PythonAdapter,
)
from naas_abi_core.services.keyvalue.KeyValueService import KeyValueService


def test_cache_keyvalue_lifecycle():
    cache = CacheKeyValueAdapter(KeyValueService(PythonAdapter()))
    first = CachedData(key="key", data="first", data_type=DataType.TEXT)
    assert cache.set_if_absent("key", first)
    assert not cache.set_if_absent("key", first)
    assert cache.get("key").data == "first"
    cache.set("key", CachedData(key="key", data="updated", data_type=DataType.TEXT))
    assert cache.exists("key")
    assert cache.get("key").data == "updated"
    cache.delete("key")
    assert not cache.exists("key")
    with pytest.raises(CacheNotFoundError):
        cache.get("key")

    with pytest.raises(CacheNotFoundError):
        cache.delete("key")


from naas_abi_core.services.cache.tests.cache__secondary_adapter__generic_test import (
    GenericCacheAdapterTest,
)


class TestCacheKeyValueAdapterContract(GenericCacheAdapterTest):
    @pytest.fixture
    def adapter(self):
        return CacheKeyValueAdapter(KeyValueService(PythonAdapter()))


def test_list_keys_ignores_other_keys_in_the_store():
    kv = KeyValueService(PythonAdapter())
    kv.set("cache:not-a-digest", b"{}")
    kv.set("session:abc", b"x")
    cache = CacheKeyValueAdapter(kv)
    cache.set("real", CachedData(key="real", data="v", data_type=DataType.TEXT))

    assert cache.list_keys("", limit=10).keys == ("real",)
