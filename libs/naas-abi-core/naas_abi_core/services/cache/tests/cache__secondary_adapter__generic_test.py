"""Behaviour every ``ICacheAdapter`` must have; each adapter's test subclasses it."""

from abc import ABC, abstractmethod
from uuid import uuid4

import pytest
from naas_abi_core.services.cache.CachePort import (
    CachedData,
    CacheNotFoundError,
    DataType,
)


def put(
    adapter, key: str, data: str = "v", data_type: DataType = DataType.TEXT
) -> None:
    adapter.set(key, CachedData(key=key, data=data, data_type=data_type))


class GenericCacheAdapterTest(ABC):
    """fixture ``adapter``: a working ICacheAdapter; it may hold other keys."""

    @pytest.fixture
    @abstractmethod
    def adapter(self):
        raise NotImplementedError()

    @staticmethod
    def _seed(adapter) -> tuple[str, list[str]]:
        # Logical keys with characters a storage name could not hold as is.
        prefix = f"generic:{uuid4()}:"
        keys = [f"{prefix}{name}" for name in ("c", "a/x y", "b", "a/z", "é")]
        for key in keys:
            put(adapter, key)
        return prefix, sorted(keys)

    def test_set_get_exists_delete(self, adapter):
        key = f"generic:{uuid4()}"
        put(adapter, key, data='{"a": 1}', data_type=DataType.JSON)

        assert adapter.exists(key) is True
        entry = adapter.get(key)
        assert (entry.key, entry.data, entry.data_type) == (
            key,
            '{"a": 1}',
            DataType.JSON,
        )

        adapter.delete(key)
        assert adapter.exists(key) is False
        with pytest.raises(CacheNotFoundError):
            adapter.get(key)

    def test_list_keys_returns_logical_keys_in_order(self, adapter):
        prefix, keys = self._seed(adapter)

        page = adapter.list_keys(prefix, limit=100)

        assert page.keys == tuple(keys)
        assert page.next_after is None
        assert adapter.list_keys(f"{prefix}a/", limit=100).keys == (
            f"{prefix}a/x y",
            f"{prefix}a/z",
        )

    def test_list_keys_pages_strictly_after_the_cursor(self, adapter):
        prefix, keys = self._seed(adapter)

        seen, after = [], None
        for _ in range(10):
            page = adapter.list_keys(prefix, limit=2, after=after)
            assert len(page.keys) <= 2
            seen += page.keys
            after = page.next_after
            if after is None:
                break

        assert seen == keys

    def test_list_keys_forgets_deleted_keys(self, adapter):
        prefix, keys = self._seed(adapter)

        adapter.delete(keys[0])

        assert adapter.list_keys(prefix, limit=100).keys == tuple(keys[1:])

    def test_list_keys_rejects_an_out_of_range_limit(self, adapter):
        with pytest.raises(ValueError):
            adapter.list_keys("", limit=0)
