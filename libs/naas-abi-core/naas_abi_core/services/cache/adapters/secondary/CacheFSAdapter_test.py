from concurrent.futures import ThreadPoolExecutor

from naas_abi_core.services.cache.adapters.secondary.CacheFSAdapter import (
    CacheFSAdapter,
)
from naas_abi_core.services.cache.CachePort import CachedData, DataType


def test_persistence_across_restart(tmp_path):
    adapter = CacheFSAdapter(str(tmp_path / "cache"))
    adapter.set("k", CachedData(key="k", data="v", data_type=DataType.TEXT))

    restarted = CacheFSAdapter(str(tmp_path / "cache"))
    assert restarted.get("k").data == "v"


def test_atomic_concurrent_writes(tmp_path):
    adapter = CacheFSAdapter(str(tmp_path / "cache"))

    def _write(i: int) -> None:
        adapter.set(
            "k",
            CachedData(key="k", data=f"v-{i}", data_type=DataType.TEXT),
        )

    with ThreadPoolExecutor(max_workers=8) as executor:
        list(executor.map(_write, range(20)))

    result = adapter.get("k")
    assert result.data.startswith("v-")


def test_set_if_absent(tmp_path):
    adapter = CacheFSAdapter(str(tmp_path / "cache"))

    first = adapter.set_if_absent(
        "k", CachedData(key="k", data="v1", data_type=DataType.TEXT)
    )
    second = adapter.set_if_absent(
        "k", CachedData(key="k", data="v2", data_type=DataType.TEXT)
    )

    assert first is True
    assert second is False
    assert adapter.get("k").data == "v1"


import pytest
from naas_abi_core.services.cache.tests.cache__secondary_adapter__generic_test import (
    GenericCacheAdapterTest,
    put,
)


class TestCacheFSAdapterContract(GenericCacheAdapterTest):
    @pytest.fixture
    def adapter(self, tmp_path):
        return CacheFSAdapter(str(tmp_path / "cache"))


def test_list_keys_reads_keys_longer_than_the_file_head(tmp_path):
    adapter = CacheFSAdapter(str(tmp_path / "cache"))
    long_key = "k" * 10_000
    put(adapter, long_key, data="x" * 50_000)
    put(adapter, "short")

    assert adapter.list_keys("", limit=10).keys == (long_key, "short")


def test_list_keys_ignores_foreign_and_temporary_files(tmp_path):
    adapter = CacheFSAdapter(str(tmp_path / "cache"))
    put(adapter, "real")
    (tmp_path / "cache" / "tmpabc123").write_text("{}")
    (tmp_path / "cache" / "README").write_text("not an entry")

    assert adapter.list_keys("", limit=10).keys == ("real",)
