from concurrent.futures import ThreadPoolExecutor

from naas_abi_core.services.cache.CachePort import CachedData, DataType
from naas_abi_core.services.cache.adapters.secondary.CacheFSAdapter import (
    CacheFSAdapter,
)


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
