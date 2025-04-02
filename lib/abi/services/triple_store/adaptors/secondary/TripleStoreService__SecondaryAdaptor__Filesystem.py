from lib.abi.services.triple_store.TripleStorePorts import ITripleStorePort
from abi.services.triple_store.adaptors.secondary.base.TripleStoreService__SecondaryAdaptor__FileBase import TripleStoreService__SecondaryAdaptor__FileBase
from rdflib import Graph
from typing import List, Dict, Tuple, Any
import os
class TripleStoreService__SecondaryAdaptor__Filesystem(ITripleStorePort, TripleStoreService__SecondaryAdaptor__FileBase):
    __store_path: str
    __triples_path: str
    
    def __init__(self, store_path: str, triples_path: str = "triples"):
        self.__store_path = store_path
        self.__triples_path = triples_path

        os.makedirs(os.path.join(self.__store_path, self.__triples_path), exist_ok=True)
    
    def __merge_graphs(self, graphs: List[Graph]) -> Graph:
        merged_graph = Graph()
        for graph in graphs:
            merged_graph += graph
            
        return merged_graph
    
    def hash_triples_path(self, hash_value: str) -> str:
        return os.path.join(self.__store_path, 'triples', f'{hash_value}.ttl' if not hash_value.endswith('.ttl') else hash_value)
    
    ## File System Methods
    
    def insert(self, triples: Graph):
        triples_by_subject : Dict[Any, List[Tuple[Any, Any]]] = self.triples_by_subject(triples)

        for subject in triples_by_subject:
            subject_hash = self.iri_hash(subject)
            
            if not os.path.exists(self.hash_triples_path(subject_hash)):
                graph = Graph()
                
                for prefix, namespace in triples.namespaces():
                    graph.bind(prefix, namespace)
            else:
                graph = Graph().parse(self.hash_triples_path(subject_hash), format='turtle')
            
            for p, o in triples_by_subject[subject]:
                graph.add((subject, p, o))
            
            graph.serialize(destination=self.hash_triples_path(subject_hash), format='turtle')
    
    def remove(self, triples: Graph):
        triples_by_subject : Dict[Any, List[Tuple[Any, Any]]] = self.triples_by_subject(triples)
        
        for subject in triples_by_subject:
            subject_hash = self.iri_hash(subject)
            
            if os.path.exists(self.hash_triples_path(subject_hash)):
                graph = Graph().parse(self.hash_triples_path(subject_hash), format='turtle')
                
                for p, o in triples_by_subject[subject]:
                    graph.remove((subject, p, o))
                
                graph.serialize(destination=self.hash_triples_path(subject_hash), format='turtle')
    
    ## Ontology Methods

    def get(self) -> Graph:
        triples = Graph()
        
        for file in os.listdir(os.path.join(self.__store_path, 'triples')):
            g = Graph().parse(self.hash_triples_path(file), format='turtle')
            
            for prefix, namespace in g.namespaces():
                triples.bind(prefix, namespace)
            
            triples += g
        return triples
        

    def query(self, query: str) -> Graph:
        aggregate_graph = self.get()
        
        return aggregate_graph.query(query)

    

