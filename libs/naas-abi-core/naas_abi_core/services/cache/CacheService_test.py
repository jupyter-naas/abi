import datetime
import time

from naas_abi_core.services.cache.CachePort import (
    CachedData,
    CacheNotFoundError,
    DataType,
    ICacheAdapter,
)
from naas_abi_core.services.cache.CacheService import CacheService


class CacheMemoryAdapter(ICacheAdapter):
    def __init__(self):
        self.cache = {}

    def get(self, key: str) -> CachedData:
        if key not in self.cache:
            raise CacheNotFoundError(f"Cache not found: {key}")
        return self.cache[key]

    def set(self, key: str, value: CachedData) -> None:
        self.cache[key] = value

    def delete(self, key: str) -> None:
        if key not in self.cache:
            raise CacheNotFoundError(f"Cache not found: {key}")
        del self.cache[key]

    def exists(self, key: str) -> bool:
        return key in self.cache


def test_cache_service():
    cache_service = CacheService(CacheMemoryAdapter())

    salt = "good"

    @cache_service(
        lambda x: f"key_{x}",
        cache_type=DataType.TEXT,
        ttl=datetime.timedelta(seconds=1),
    )
    def get_text_data(x: str) -> str:
        """Get text data"""
        return f"data_{x}_{salt}"

    # First call will not be cached and will populate it
    assert get_text_data("test") == "data_test_good"

    # We change the salt, so if the method is executed again, the assertion will fail. Here we want to
    # make sure that we are getting the data from the cache.
    salt = "bad"

    assert get_text_data("test") == "data_test_good"

    # We sleep for 1 second to make sure the cache will expire.
    time.sleep(1)

    assert get_text_data("test") == "data_test_bad"


def test_non_matching_arguments():
    cache_service = CacheService(CacheMemoryAdapter())

    @cache_service(
        lambda x, z: f"key_{x}_{z}",
        cache_type=DataType.TEXT,
        ttl=datetime.timedelta(seconds=1),
    )
    def get_text_data(x: str, y: str, z: str = "toto") -> str:
        """Get text data"""
        return f"{x}_{y}_{z}"

    assert get_text_data("test", "test", "tati") == "test_test_tati"
    assert get_text_data(x="test", y="tata", z="tutu") == "test_tata_tutu"
    assert get_text_data(x="test", y="toto") == "test_toto_toto"

    # There is cache
    assert get_text_data(x="test", y="yolo") == "test_toto_toto"

    # Same but for cache refresh
    assert (
        get_text_data(x="test", y="yolo", force_cache_refresh=True) == "test_yolo_toto"
    )
