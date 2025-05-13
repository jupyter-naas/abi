from lib.abi.services.triple_store.TripleStoreService import TripleStoreService
from lib.abi.services.triple_store.adaptors.secondary.TripleStoreService__SecondaryAdaptor__ObjectStorage import (
    TripleStoreService__SecondaryAdaptor__NaasStorage,
)
from lib.abi.services.triple_store.adaptors.secondary.TripleStoreService__SecondaryAdaptor__Filesystem import (
    TripleStoreService__SecondaryAdaptor__Filesystem,
)
from lib.abi.services.object_storage.ObjectStorageFactory import (
    ObjectStorageFactory,
    ObjectStorageService,
)


class TripleStoreFactory:
    @staticmethod
    def TripleStoreServiceNaas(
        naas_api_key: str,
        workspace_id: str,
        storage_name: str,
        base_prefix: str = "ontologies",
    ) -> TripleStoreService:
        """Creates an TripleStoreService using Naas object storage.

        Args:
            naas_api_key (str): API key for Naas service
            workspace_id (str): Workspace ID for Naas storage
            storage_name (str): Name of storage to use
            base_prefix (str): Base prefix for object paths. Defaults to "ontologies"

        Returns:
            TripleStoreService: Configured ontology store service using Naas storage
        """
        object_service = ObjectStorageFactory.ObjectStorageServiceNaas(
            naas_api_key=naas_api_key,
            workspace_id=workspace_id,
            storage_name=storage_name,
            base_prefix=base_prefix,
        )
        return TripleStoreService(
            TripleStoreService__SecondaryAdaptor__NaasStorage(object_service)
        )

    @staticmethod
    def TripleStoreServiceFilesystem(path: str) -> TripleStoreService:
        return TripleStoreService(
            TripleStoreService__SecondaryAdaptor__Filesystem(path)
        )
