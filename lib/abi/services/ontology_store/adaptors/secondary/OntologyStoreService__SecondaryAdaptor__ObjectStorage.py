from lib.abi.services.ontology_store.OntologyStorePorts import IOntologyStorePort, OntologyNotFoundError
from lib.abi.services.object_storage.ObjectStorageService import ObjectStorageService
from lib.abi.services.object_storage.ObjectStoragePort import Exceptions as ObjectStorageExceptions

from rdflib import Graph
from typing import List

class OntologyStoreService__SecondaryAdaptor__NaasStorage(IOntologyStorePort):
    
    __object_storage_service : ObjectStorageService
    
    def __init__(self, object_storage_service: ObjectStorageService):
        self.__object_storage_service = object_storage_service
        
    def store(self, name: str, ontology: Graph):
        if not name.endswith('.ttl'):
            name = f"{name}.ttl"
        serialized_ontology = ontology.serialize(format='turtle').encode('utf-8')
        self.__object_storage_service.put_object(prefix="", key=name, content=serialized_ontology)
    
    def get(self, name: str) -> Graph:
        try:
            obj = self.__object_storage_service.get_object(prefix="", key=name if name.endswith('.ttl') else f"{name}.ttl")
            content = obj.decode('utf-8')

            return Graph().parse(data=content, format='turtle')
        except ObjectStorageExceptions.ObjectNotFound:
            raise OntologyNotFoundError(f"Ontology {name} not found")
    
    def get_by_names(self, names: List[str]) -> List[Graph]:
        graphs = [self.get(name) for name in names]
        
        merged_graph = Graph()
        for graph in graphs:
            merged_graph += graph
            
        return merged_graph

    def get_all(self) -> Graph:
        objects = self.__object_storage_service.list_objects()
        graphs = [self.get(name) for name in objects]
        
        merged_graph = Graph()
        for graph in graphs:
            merged_graph += graph

        return merged_graph

    def query(self, query: str) -> Graph:
        return self.get_all().query(query)
    
    def query_by_name(self, name: str, query: str) -> Graph:
        return self.get(name).query(query)
    
    def delete(self, name: str):
        self.__object_storage_service.delete_object(key=name if name.endswith('.ttl') else f"{name}.ttl")
    
    def list_ontologies(self) -> List[str]:
        return [e if not e.endswith('.ttl') else e[:-4] for e in self.__object_storage_service.list_objects()]