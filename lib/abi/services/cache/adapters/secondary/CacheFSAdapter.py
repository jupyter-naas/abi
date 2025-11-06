from abi.services.cache.CachePort import ICacheAdapter, CachedData, CacheNotFoundError
import os
import json
import hashlib

class CacheFSAdapter(ICacheAdapter):
    def __init__(self, cache_dir: str):
        self.cache_dir = cache_dir
        
        if not os.path.exists(self.cache_dir):
            os.makedirs(self.cache_dir)
            
    def __key_to_sha256(self, key: str) -> str:
        return hashlib.sha256(key.encode()).hexdigest()
        
    def get(self, key: str) -> CachedData:        
        if not os.path.exists(os.path.join(self.cache_dir, self.__key_to_sha256(key))):
            raise CacheNotFoundError(f"Cache file not found: {key}")
        
        with open(os.path.join(self.cache_dir, self.__key_to_sha256(key)), "r") as f:
            return CachedData(**json.load(f))
    
    def set(self, key: str, value: CachedData) -> None:
        with open(os.path.join(self.cache_dir, self.__key_to_sha256(key)), "w") as f:
            json.dump(value.model_dump(), f, indent=4)
    
    def delete(self, key: str) -> None:
        if not os.path.exists(os.path.join(self.cache_dir, self.__key_to_sha256(key))):
            raise CacheNotFoundError(f"Cache file not found: {key}")
        os.remove(os.path.join(self.cache_dir, self.__key_to_sha256(key)))
        
    def exists(self, key: str) -> bool:
        return os.path.exists(os.path.join(self.cache_dir, self.__key_to_sha256(key)))
    