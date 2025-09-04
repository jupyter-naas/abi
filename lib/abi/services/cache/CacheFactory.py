from abi.services.cache.CacheService import CacheService
from abi.services.cache.adapters.secondary.CacheFSAdapter import CacheFSAdapter

from abi.utils.Storage import find_storage_folder, NoStorageFolderFound
import os

class CacheFactory:
    @staticmethod
    def CacheFS_find_storage(subpath: str = "cache", needle: str = "storage") -> CacheService:
        if not subpath.startswith("cache"):
            subpath = os.path.join("cache", subpath)
        
        try:
            return CacheService(CacheFSAdapter(os.path.join(find_storage_folder(os.getcwd(), needle), subpath)))
        except NoStorageFolderFound as _:
            # Create a "storage" folder for the cache
            os.makedirs(os.path.join(os.getcwd(), "storage"), exist_ok=True)
            return CacheService(CacheFSAdapter(os.path.join(find_storage_folder(os.getcwd(), needle), subpath)))