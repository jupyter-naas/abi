from lib.abi.services.triple_store.TripleStorePorts import ITripleStoreService, ITripleStorePort, OntologyEvent
from rdflib import Graph, RDF, RDFS
from typing import Callable, List, Tuple
import uuid
import pydash

OWL_URL = "https://www.w3.org/2002/07/owl"
CCO_URL = "https://raw.githubusercontent.com/CommonCoreOntology/CommonCoreOntologies/refs/heads/develop/src/cco-merged/CommonCoreOntologiesMerged.ttl"
BFO_URL = "https://raw.githubusercontent.com/BFO-ontology/BFO-2020/refs/heads/master/src/owl/bfo-core.ttl"

class TripleStoreService(ITripleStoreService):
    """TripleStoreService provides CRUD operations and SPARQL querying capabilities for ontologies.
    
    This service acts as a facade for ontology storage and retrieval operations. It handles storing,
    retrieving, merging and querying of RDF ontologies while providing optional filtering of 
    non-named individuals.
    
    Attributes:
        __ontology_adaptor (ITripleStorePort): The storage adapter implementation used for
            persisting and retrieving ontologies.
            
    Example:
        >>> store = TripleStoreService(FileSystemTripleStore("ontologies/"))
        >>> ontology = Graph()
        >>> # ... populate ontology ...
        >>> store.store("my_ontology", ontology)
        >>> results = store.query("SELECT ?s WHERE { ?s a owl:Class }")
    """
    def __init__(self, ontology_adaptor: ITripleStorePort, views: List[Tuple[str, str, str]] = [
        (None, RDF.type, None)
    ], load_base_ontologies: bool = False):
        self.__ontology_adaptor = ontology_adaptor
        self.__event_listeners = {}
        self.__views = views
        
        self.init_views()
        
        if load_base_ontologies:
            # Load OWL
            self.insert(Graph().parse(OWL_URL, format='turtle'))
            
            # Load BFO
            self.insert(Graph().parse(BFO_URL, format='turtle'))
            
                # Load CCO
            self.insert(Graph().parse(CCO_URL, format='turtle'))
        
        

    def init_views(self):
        for view in self.__views:
            self.subscribe(view, OntologyEvent.INSERT, lambda event, triple: self.__ontology_adaptor.handle_view_event(view, event, triple))
            self.subscribe(view, OntologyEvent.DELETE, lambda event, triple: self.__ontology_adaptor.handle_view_event(view, event, triple))

    def insert(self, triples: Graph):
        # Insert the triples into the store
        self.__ontology_adaptor.insert(triples)
        
        # Notify listeners of the insert
        for s, p, o in triples.triples((None, None, None)):
            for ss, sp, so in self.__event_listeners:
                if (ss is None or str(ss) == str(s)) and (sp is None or str(sp) == str(p)) and (so is None or str(so) == str(o)):
                    if OntologyEvent.INSERT in self.__event_listeners[ss, sp, so]:
                        for _, callback in self.__event_listeners[ss, sp, so][OntologyEvent.INSERT]:
                            callback(OntologyEvent.INSERT, (s, p, o))
                
    def remove(self, triples: Graph):
        # Remove the triples from the store
        self.__ontology_adaptor.remove(triples)

        # Notify listeners of the delete
        for s, p, o in triples.triples((None, None, None)):
            for ss, sp, so in self.__event_listeners:
                if (ss is None or str(ss) == str(s)) and (sp is None or str(sp) == str(p)) and (so is None or str(so) == str(o)):
                    if OntologyEvent.DELETE in self.__event_listeners[ss, sp, so]:
                        for _, callback in self.__event_listeners[ss, sp, so][OntologyEvent.DELETE]:
                            callback(OntologyEvent.DELETE, (s, p, o))

    def get(self) -> Graph:
        return self.__ontology_adaptor.get()

    def query(self, query: str) -> Graph:
        return self.__ontology_adaptor.query(query)
    
    def query_view(self, view: str, query: str) -> Graph:
        return self.__ontology_adaptor.query_view(view, query)
    
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
