from lib.abi.services.ontology_store.OntologyStoreService import OntologyStoreService
from lib.abi.services.ontology_store.adaptors.secondary.OntologyStoreService__SecondaryAdaptor__ObjectStorage import OntologyStoreService__SecondaryAdaptor__NaasStorage
from lib.abi.services.ontology_store.adaptors.secondary.OntologyStoreService__SecondaryAdaptor__Filesystem import OntologyStoreService__SecondaryAdaptor__Filesystem
from lib.abi.services.object_storage.ObjectStorageFactory import ObjectStorageFactory

class OntologyStoreFactory:
    
    @staticmethod 
    def OntologyStoreServiceNaas(naas_api_key: str, workspace_id: str, storage_name: str, base_prefix: str = "ontologies") -> OntologyStoreService:
        """Creates an OntologyStoreService using Naas object storage.
        
        Args:
            naas_api_key (str): API key for Naas service
            workspace_id (str): Workspace ID for Naas storage
            storage_name (str): Name of storage to use
            base_prefix (str): Base prefix for object paths. Defaults to "ontologies"
            
        Returns:
            OntologyStoreService: Configured ontology store service using Naas storage
        """
        object_service = ObjectStorageFactory.ObjectStorageServiceNaas(
            naas_api_key=naas_api_key,
            workspace_id=workspace_id, 
            storage_name=storage_name,
            base_prefix=base_prefix
        )
        return OntologyStoreService(OntologyStoreService__SecondaryAdaptor__NaasStorage(object_service))


    @staticmethod
    def OntologyStoreServiceFilesystem(path: str) -> OntologyStoreService:
        return OntologyStoreService(OntologyStoreService__SecondaryAdaptor__Filesystem(path))   