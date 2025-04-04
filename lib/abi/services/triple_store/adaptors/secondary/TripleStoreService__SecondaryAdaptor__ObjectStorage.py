from lib.abi.services.triple_store.TripleStorePorts import ITripleStorePort, OntologyEvent
from lib.abi.services.object_storage.ObjectStorageService import ObjectStorageService
from lib.abi.services.object_storage.ObjectStoragePort import Exceptions as ObjectStorageExceptions
from lib.abi.services.triple_store.adaptors.secondary.base.TripleStoreService__SecondaryAdaptor__FileBase import TripleStoreService__SecondaryAdaptor__FileBase
from rdflib import Graph
from typing import List, Dict, Tuple, Any
import os

class TripleStoreService__SecondaryAdaptor__NaasStorage(ITripleStorePort, TripleStoreService__SecondaryAdaptor__FileBase):
    
    __object_storage_service : ObjectStorageService

    __triples_prefix : str
    
    __live_graph : Graph
    
    def __init__(self, object_storage_service: ObjectStorageService, triples_prefix: str = "triples"):
        self.__object_storage_service = object_storage_service
        self.__triples_prefix = triples_prefix
        
        self.__live_graph = self.load()
    
    def load_triples(self, subject_hash: str) -> Graph:
        obj = self.__object_storage_service.get_object(prefix=self.__triples_prefix, key=f"{subject_hash}.ttl")

        content = obj.decode('utf-8')
        
        return Graph().parse(data=content, format='turtle')
     
    def store(self, name: str, triples: Graph):
        serialized_triples = triples.serialize(format='turtle').encode('utf-8')
        self.__object_storage_service.put_object(prefix=self.__triples_prefix, key=f"{name}.ttl", content=serialized_triples)
     
    def insert(self, triples: Graph):
        triples_by_subject : Dict[Any, List[Tuple[Any, Any]]] = self.triples_by_subject(triples)

        for subject in triples_by_subject:
            subject_hash = self.iri_hash(subject)
            
            try:
                graph = self.load_triples(subject_hash)
            except ObjectStorageExceptions.ObjectNotFound:
                graph = Graph()
                for prefix, namespace in triples.namespaces():
                    graph.bind(prefix, namespace)

            for p, o in triples_by_subject[subject]:
                graph.add((subject, p, o))
            
            self.store(subject_hash, graph)
        
        for prefix, namespace in triples.namespaces():
            self.__live_graph.bind(prefix, namespace)
            
        self.__live_graph += triples
    
    
    def remove(self, triples: Graph):
        triples_by_subject : Dict[Any, List[Tuple[Any, Any]]] = self.triples_by_subject(triples)

        for subject in triples_by_subject:
            subject_hash = self.iri_hash(subject)
            
            try:
                graph = self.load_triples(subject_hash)
                for p, o in triples_by_subject[subject]:
                    graph.add((subject, p, o))
                
                self.store(subject_hash, graph)
            except ObjectStorageExceptions.ObjectNotFound:
                pass
        
        for prefix, namespace in triples.namespaces():
            self.__live_graph.bind(prefix, namespace)
            
        self.__live_graph -= triples
    
    def load(self) -> Graph:
        triples = Graph()
        
        try:
            for obj in self.__object_storage_service.list_objects(prefix=self.__triples_prefix):
                g = self.load_triples(obj)
                for prefix, namespace in g.namespaces():
                    triples.bind(prefix, namespace)
                triples += g
        except ObjectStorageExceptions.ObjectNotFound:
            pass
            
        return triples

    def get(self) -> Graph:
        return self.__live_graph

    def query(self, query: str) -> Graph:
        return self.get().query(query)
    
    def query_view(self, view: str, query: str) -> Graph:
        return self.get().query(query)
    
    def handle_view_event(self, view: Tuple[str, str, str], event: OntologyEvent, triple: Tuple[str, str, str]):
        pass
    
    