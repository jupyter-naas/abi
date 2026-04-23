from naas_abi_core.services.cache.CachePort import CachedData, DataType
from naas_abi_core.services.cache.adapters.secondary.CacheObjectStorageAdapter import (
    CacheObjectStorageAdapter,
)
from naas_abi_core.services.object_storage.ObjectStorageService import (
    ObjectStorageService,
)
from naas_abi_core.services.object_storage.adapters.secondary.ObjectStorageSecondaryAdapterFS import (
    ObjectStorageSecondaryAdapterFS,
)


def _make_adapter(tmp_path):
    storage = ObjectStorageService(
        ObjectStorageSecondaryAdapterFS(str(tmp_path / "storage"))
    )
    return CacheObjectStorageAdapter(storage, prefix="cache")


def test_roundtrip(tmp_path):
    adapter = _make_adapter(tmp_path)

    adapter.set("k", CachedData(key="k", data="v", data_type=DataType.TEXT))

    result = adapter.get("k")
    assert result.key == "k"
    assert result.data == "v"
    assert result.data_type == DataType.TEXT


def test_exists_and_delete(tmp_path):
    adapter = _make_adapter(tmp_path)
    adapter.set("k", CachedData(key="k", data="v", data_type=DataType.TEXT))

    assert adapter.exists("k") is True
    adapter.delete("k")
    assert adapter.exists("k") is False


def test_set_if_absent(tmp_path):
    adapter = _make_adapter(tmp_path)

    first = adapter.set_if_absent(
        "k", CachedData(key="k", data="v1", data_type=DataType.TEXT)
    )
    second = adapter.set_if_absent(
        "k", CachedData(key="k", data="v2", data_type=DataType.TEXT)
    )

    assert first is True
    assert second is False
    assert adapter.get("k").data == "v1"


def test_concurrent_set_if_absent_produces_valid_entry(tmp_path) -> None:
    """Simulate two threads racing to write the same key.

    Object storage set_if_absent is best-effort (not atomic), but for the
    embedding cache use case both writers produce identical content, so the
    final cache entry must always be valid regardless of who wins.
    """
    import threading

    adapter = _make_adapter(tmp_path)
    results: list[bool] = []
    lock = threading.Lock()

    def writer(data_value: str) -> None:
        result = adapter.set_if_absent(
            "shared-key",
            CachedData(key="shared-key", data=data_value, data_type=DataType.TEXT),
        )
        with lock:
            results.append(result)

    # Kick off two concurrent writers with identical content (same sha256 → same payload)
    identical_value = "deterministic-embedding-payload"
    t1 = threading.Thread(target=writer, args=(identical_value,))
    t2 = threading.Thread(target=writer, args=(identical_value,))
    t1.start()
    t2.start()
    t1.join()
    t2.join()

    # The entry must be present and have valid content
    stored = adapter.get("shared-key")
    assert stored.data == identical_value
    # Both calls together should have returned True at least once
    assert any(results)


def test_large_json_payload_roundtrip(tmp_path) -> None:
    """JSON payloads containing embedding vectors (large lists of floats) survive a roundtrip."""
    import json

    adapter = _make_adapter(tmp_path)
    large_vectors = [[float(i * 0.001 + j) for j in range(256)] for i in range(20)]
    payload = json.dumps({"chunks": ["chunk"] * 20, "vectors": large_vectors})

    adapter.set("big-key", CachedData(key="big-key", data=payload, data_type=DataType.JSON))
    result = adapter.get("big-key")

    recovered = json.loads(result.data)
    assert len(recovered["chunks"]) == 20
    assert len(recovered["vectors"]) == 20
    assert len(recovered["vectors"][0]) == 256
