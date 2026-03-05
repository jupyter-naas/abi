from concurrent.futures import ThreadPoolExecutor

from naas_abi_core.services.object_storage.adapters.secondary.ObjectStorageSecondaryAdapterFS import (
    ObjectStorageSecondaryAdapterFS,
)


def test_persistence_across_restart(tmp_path):
    base_path = str(tmp_path / "storage")
    adapter = ObjectStorageSecondaryAdapterFS(base_path=base_path)
    adapter.put_object("objects", "k.txt", b"hello")

    restarted = ObjectStorageSecondaryAdapterFS(base_path=base_path)
    assert restarted.get_object("objects", "k.txt") == b"hello"


def test_atomic_concurrent_put(tmp_path):
    adapter = ObjectStorageSecondaryAdapterFS(base_path=str(tmp_path / "storage"))

    def _put(i: int) -> None:
        adapter.put_object("objects", "k.bin", f"value-{i}".encode("utf-8"))

    with ThreadPoolExecutor(max_workers=8) as executor:
        list(executor.map(_put, range(30)))

    data = adapter.get_object("objects", "k.bin")
    assert data.startswith(b"value-")
