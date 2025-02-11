import os

from lib.abi.services.object_storage.ObjectStorageFactory import ObjectStorageFactory, ObjectStorageService
from lib.abi.services.ontology_store.OntologyFactory import OntologyStoreFactory, OntologyStoreService

class Services:
    _instance = None
    
    storage_service: ObjectStorageService
    ontology_store_service: OntologyStoreService
    
    def __new__(cls, *args, **kwargs):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
        return cls._instance
    
    def __init__(self, config, secret):
        self.config = config
        self.secret = secret
        
        if os.environ.get('ENV') == 'dev':
            self.__init_dev()
        else:
            self.__init_prod()
    
    def __init_dev(self):
        self.storage_service = ObjectStorageFactory.ObjectStorageServiceFS__find_storage()
        self.ontology_store_service = OntologyStoreFactory.OntologyStoreServiceNaas(
            naas_api_key=self.secret.get('NAAS_API_KEY'),
            workspace_id=self.config.workspace_id,
            storage_name=self.config.storage_name
        )
    
    def __init_prod(self):
        self.storage_service = ObjectStorageFactory.ObjectStorageServiceNaas(
            naas_api_key=self.secret.get('NAAS_API_KEY'),
            workspace_id=self.config.workspace_id,
            storage_name=self.config.storage_name
        )
        self.ontology_store_service = OntologyStoreFactory.OntologyStoreServiceNaas(
            naas_api_key=self.secret.get('NAAS_API_KEY'),
            workspace_id=self.config.workspace_id,
            storage_name=self.config.storage_name
        )

services : Services = None

def init_services(config, secret):
    global services
    services = Services(config, secret)
    return services