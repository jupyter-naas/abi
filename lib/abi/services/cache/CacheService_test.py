from lib.abi.services.cache.CacheService import CacheService
from lib.abi.services.cache.CachePort import ICacheAdapter, CachedData, DataType, CacheNotFoundError
import datetime
import time

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
    
    @cache_service.cache(lambda x: f"key_{x}", cache_type=DataType.TEXT, ttl=datetime.timedelta(seconds=1))
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