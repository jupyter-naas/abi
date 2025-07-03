from abi.services.cache.CacheService import CacheService
from abi.services.cache.adapters.secondary.CacheFSAdapter import CacheFSAdapter

from abi.utils.Storage import find_storage_folder
import os

class CacheFactory:
    @staticmethod
    def CacheFS_find_storage(subpath: str = "cache", needle: str = "storage") -> CacheService:
        print(os.getcwd())
        if not subpath.startswith("cache"):
            subpath = os.path.join("cache", subpath)
        return CacheService(CacheFSAdapter(os.path.join(find_storage_folder(os.getcwd(), needle), subpath)))