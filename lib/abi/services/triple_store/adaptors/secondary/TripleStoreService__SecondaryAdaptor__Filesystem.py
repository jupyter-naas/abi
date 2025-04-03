from lib.abi.services.triple_store.TripleStorePorts import ITripleStorePort, OntologyEvent, Exceptions
from abi.services.triple_store.adaptors.secondary.base.TripleStoreService__SecondaryAdaptor__FileBase import TripleStoreService__SecondaryAdaptor__FileBase
from rdflib import Graph, RDFS
from typing import List, Dict, Tuple, Any
import os
class TripleStoreService__SecondaryAdaptor__Filesystem(ITripleStorePort, TripleStoreService__SecondaryAdaptor__FileBase):
    __store_path: str
    __triples_path: str
    
    __live_graph : Graph
    
    def __init__(self, store_path: str, triples_path: str = "triples"):
        self.__store_path = store_path
        self.__triples_path = triples_path
        
        os.makedirs(os.path.join(self.__store_path, self.__triples_path), exist_ok=True)
        
        self.__live_graph = self.load()
        
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
        
        for prefix, namespace in triples.namespaces():
            self.__live_graph.bind(prefix, namespace)
        
        # Update the live graph
        self.__live_graph += triples

    def remove(self, triples: Graph):
        triples_by_subject : Dict[Any, List[Tuple[Any, Any]]] = self.triples_by_subject(triples)
        
        for subject in triples_by_subject:
            subject_hash = self.iri_hash(subject)
            
            if os.path.exists(self.hash_triples_path(subject_hash)):
                graph = Graph().parse(self.hash_triples_path(subject_hash), format='turtle')
                
                for p, o in triples_by_subject[subject]:
                    graph.remove((subject, p, o))
                
                graph.serialize(destination=self.hash_triples_path(subject_hash), format='turtle')

        # Update the live graph
        self.__live_graph -= triples

    ## Ontology Methods

    def get(self) -> Graph:
        return self.__live_graph
    
    def load(self) -> Graph:
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
    
    def query_view(self, view: str, query: str) -> Graph:
        if os.path.exists(os.path.join(self.__store_path, 'views', view)):
            aggregate_graph = Graph()
            
            for file in os.listdir(os.path.join(self.__store_path, 'views', view)):
                g = Graph().parse(os.path.join(self.__store_path, 'views', view, file), format='turtle')
                
                for prefix, namespace in g.namespaces():
                    aggregate_graph.bind(prefix, namespace)
                
                aggregate_graph += g
                
            return aggregate_graph.query(query)
        else:
            raise Exceptions.ViewNotFoundError(f"View {view} not found")
    
    def handle_view_event(self, view: Tuple[str, str, str], event: OntologyEvent, triple: Tuple[str, str, str]):
        s, _, o = triple
        
        partition_hash = self.iri_hash(o)
        
        if os.path.exists(self.hash_triples_path(partition_hash)):
            graph = Graph().parse(self.hash_triples_path(partition_hash), format='turtle')
            
            label = graph.value(subject=o, predicate=RDFS.label)
            object_id = str(o).split("/")[-1].split("#")[-1]
            
            dir_name = f"{label}_{object_id}"
            
            os.makedirs(os.path.join(self.__store_path, 'views', dir_name), exist_ok=True)
            
            if event == OntologyEvent.INSERT:
                try:
                    # Create symbolic link
                    os.symlink(os.path.join('..', '..', 'triples', f'{self.iri_hash(s)}.ttl'), os.path.join(self.__store_path, 'views', dir_name, f'{self.iri_hash(s)}.ttl'))
                except FileExistsError:
                    pass
            elif event == OntologyEvent.DELETE:
                # Remove symbolic link
                try:
                    os.remove(os.path.join(self.__store_path, 'views', dir_name, f'{self.iri_hash(s)}.ttl'))
                except FileNotFoundError:
                    pass
            
        
        

