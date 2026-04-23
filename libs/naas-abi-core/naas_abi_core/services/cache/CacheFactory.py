import os

from naas_abi_core.services.cache.adapters.secondary.CacheFSAdapter import (
    CacheFSAdapter,
)
from naas_abi_core.services.cache.adapters.secondary.CacheObjectStorageAdapter import (
    CacheObjectStorageAdapter,
)
from naas_abi_core.services.cache.CacheService import CacheService, TIER_COLD
from naas_abi_core.services.object_storage.ObjectStorageService import (
    ObjectStorageService,
)
from naas_abi_core.utils.Storage import NoStorageFolderFound, find_storage_folder


class CacheFactory:
    @staticmethod
    def CacheFS_find_storage(
        subpath: str = "cache", needle: str = "storage"
    ) -> CacheService:
        if not subpath.startswith("cache"):
            subpath = os.path.join("cache", subpath)

        try:
            path = os.path.join(find_storage_folder(os.getcwd(), needle), subpath)
        except NoStorageFolderFound:
            os.makedirs(os.path.join(os.getcwd(), "storage"), exist_ok=True)
            path = os.path.join(find_storage_folder(os.getcwd(), needle), subpath)

        return CacheService(adapters=[(TIER_COLD, CacheFSAdapter(path))])

    @staticmethod
    def CacheObjectStorage(
        object_storage: ObjectStorageService,
        cache_prefix: str = "cache",
    ) -> CacheService:
        return CacheService(
            adapters=[
                (
                    TIER_COLD,
                    CacheObjectStorageAdapter(
                        object_storage=object_storage, prefix=cache_prefix
                    ),
                )
            ]
        )
