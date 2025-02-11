from lib.abi.services.ontology_store.OntologyStorePorts import IOntologyStoreService, IOntologyStorePort, OntologyNotFoundError, OntologyEvent
from rdflib import Graph, BNode
from typing import List, Callable
import uuid
import pydash

class OntologyStoreService(IOntologyStoreService):
    """OntologyStoreService provides CRUD operations and SPARQL querying capabilities for ontologies.
    
    This service acts as a facade for ontology storage and retrieval operations. It handles storing,
    retrieving, merging and querying of RDF ontologies while providing optional filtering of 
    non-named individuals.
    
    Attributes:
        __ontology_adaptor (IOntologyStorePort): The storage adapter implementation used for
            persisting and retrieving ontologies.
            
    Example:
        >>> store = OntologyStoreService(FileSystemOntologyStore("ontologies/"))
        >>> ontology = Graph()
        >>> # ... populate ontology ...
        >>> store.store("my_ontology", ontology)
        >>> results = store.query("SELECT ?s WHERE { ?s a owl:Class }")
    """
    def __init__(self, ontology_adaptor: IOntologyStorePort):
        self.__ontology_adaptor = ontology_adaptor
        self.__event_listeners = {}
    
    def __filter_ontology(self, ontology: Graph) -> Graph:
        return ontology
        # Create a new graph containing only named individuals and their properties
        filtered_graph = Graph()
        
        # Get all named individuals and their properties
        for s, p, o in ontology.triples((None, None, None)):
            # Check if subject is a named individual (not a blank node)
            if not isinstance(s, BNode):
                filtered_graph.add((s, p, o))
                
        return filtered_graph
    
    def diff_graphs(self, graph1: Graph, graph2: Graph) -> Graph:
        return graph2 - graph1
    
    def store(self, name: str, ontology: Graph, individual_filter: bool = True):
        filtered_ontology = self.__filter_ontology(ontology) if individual_filter else ontology
                
        # Store the filtered graph
        self.__ontology_adaptor.store(name, filtered_ontology)
        
    def insert(self, name: str, ontology: Graph, individual_filter: bool = True):
        try:
            existing_ontology = self.get(name)
        except OntologyNotFoundError:
            existing_ontology = Graph()
        
        filtered_inserted_ontology = self.__filter_ontology(ontology) if individual_filter else ontology
        
        added = self.diff_graphs(existing_ontology, filtered_inserted_ontology)
        
        for s, p, o in added.triples((None, None, None)):
            for ss, sp, so in self.__event_listeners:
                if (ss is None or ss == s) and (sp is None or sp == p) and (so is None or so == o):
                    if OntologyEvent.INSERT in self.__event_listeners[ss, sp, so]:
                        for _, callback in self.__event_listeners[ss, sp, so][OntologyEvent.INSERT]:
                            callback(OntologyEvent.INSERT, name, (s, p, o))
                
        merged_ontology = existing_ontology + filtered_inserted_ontology

        self.store(name, merged_ontology, individual_filter=False)

    def remove(self, name: str, ontology: Graph, individual_filter: bool = True):
        existing_ontology = self.get(name)
        
        filtered_removed_ontology = self.__filter_ontology(ontology) if individual_filter else ontology
        
        removed = self.diff_graphs(filtered_removed_ontology, existing_ontology)

        for s, p, o in removed.triples((None, None, None)):
            for ss, sp, so in self.__event_listeners:
                if (ss is None or ss == s) and (sp is None or sp == p) and (so is None or so == o):
                    if OntologyEvent.DELETE in self.__event_listeners[ss, sp, so]:
                        for _, callback in self.__event_listeners[ss, sp, so][OntologyEvent.DELETE]:
                            callback(OntologyEvent.DELETE, name, (s, p, o))
        
        merged_ontology = existing_ontology - filtered_removed_ontology
        
        self.store(name, merged_ontology, individual_filter=False)
        
    def list_ontologies(self) -> List[str]:
        return self.__ontology_adaptor.list_ontologies()

    def get(self, name: str) -> Graph:
        return self.__ontology_adaptor.get(name)
    
    def get_by_names(self, names: List[str]) -> List[Graph]:
        return self.__ontology_adaptor.get_by_names(names)

    def get_all(self) -> Graph:
        return self.__ontology_adaptor.get_all()

    def query(self, query: str) -> Graph:
        return self.__ontology_adaptor.query(query)
    
    def query_by_name(self, name: str, query: str) -> Graph:
        return self.__ontology_adaptor.query_by_name(name, query)
    
    def delete(self, name: str):
        self.__ontology_adaptor.delete(name)
    
    def subscribe(self, topic: tuple, event_type: OntologyEvent, callback: Callable) -> str:
        if topic not in self.__event_listeners:
            self.__event_listeners[topic] = {}
        if event_type not in self.__event_listeners[topic]:
            self.__event_listeners[topic][event_type] = []
            
        subscription_id = str(uuid.uuid4())
            
        self.__event_listeners[topic][event_type].append((subscription_id, callback))
        
        return subscription_id
    
    def unsubscribe(self, subscription_id: str) -> None:
        for topic in self.__event_listeners:
            for event_type in self.__event_listeners[topic]:
                self.__event_listeners[topic][event_type] = pydash.filter_(self.__event_listeners[topic][event_type], lambda x: x[0] != subscription_id)

def main():
    from abi.services.ontology_store.adaptors.secondary.OntologyStoreService__SecondaryAdaptor__Filesystem import OntologyStoreService__SecondaryAdaptor__Filesystem
    ontology_store_service = OntologyStoreService(OntologyStoreService__SecondaryAdaptor__Filesystem(store_path="src/data/ontology-store"))
    
    # Create test data in Turtle format
    test_data = """
    @prefix rdf: <http://www.w3.org/1999/02/22-rdf-syntax-ns#> .
    @prefix rdfs: <http://www.w3.org/2000/01/rdf-schema#> .
    @prefix ex: <http://example.org/> .

    # Define classes
    ex:Animal a rdfs:Class .
    ex:Dog a rdfs:Class ;
        rdfs:subClassOf ex:Animal .
    ex:Cat a rdfs:Class ;
        rdfs:subClassOf ex:Animal .

    # Define named instances
    ex:Rover a ex:Dog ;
        ex:name "Rover" ;
        ex:age "5" .

    ex:Whiskers a ex:Cat ;
        ex:name "Whiskers" ;
        ex:age "3" .
    """

    # Load the turtle data into a graph
    test_graph = Graph()
    test_graph.parse(data=test_data, format="turtle")
    
    ontology_store_service.store("test", test_graph, individual_filter=False)
    
    print(ontology_store_service.list_ontologies())
    
    print(ontology_store_service.get("test").serialize(format="turtle"))
    
    for e in ontology_store_service.query("SELECT * WHERE { ?s ?p ?o }"):
        print(e)

if __name__ == "__main__":
    main()