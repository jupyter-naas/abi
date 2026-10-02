import pytest

pytest.importorskip("redis")

from naas_abi_core.services.cache.adapters.secondary.CacheRedisAdapter import (
    CacheRedisAdapter,
)
from naas_abi_core.services.cache.tests.cache__secondary_adapter__generic_test import (
    GenericCacheAdapterTest,
    put,
)


def _adapter(prefix: str = "naas:cache") -> CacheRedisAdapter:
    fakeredis = pytest.importorskip("fakeredis")
    adapter = CacheRedisAdapter(redis_url="redis://localhost:6379/0", prefix=prefix)
    adapter._client = fakeredis.FakeRedis(
        server=fakeredis.FakeServer(), decode_responses=True
    )
    return adapter


class TestCacheRedisAdapterOnFakeRedis(GenericCacheAdapterTest):
    @pytest.fixture
    def adapter(self):
        return _adapter()


def test_list_keys_stays_inside_its_namespace_and_escapes_it():
    adapter = _adapter(prefix="odd*[ns]")
    put(adapter, "mine")
    adapter._client.set("other:" + "0" * 64, '{"key": "theirs"}')
    adapter._client.set("oddX[ns]:" + "1" * 64, '{"key": "glob-lookalike"}')

    assert adapter.list_keys("", limit=10).keys == ("mine",)
