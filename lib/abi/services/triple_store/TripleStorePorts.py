from abc import ABC, abstractmethod
from rdflib import Graph
from typing import List, Callable, Dict
from enum import Enum

class Exceptions:
    class SubscriptionNotFoundError(Exception):
            pass

class ITripleStorePort(ABC):
    

    @abstractmethod
    def insert(self, triples: Graph):
        pass
    
    @abstractmethod
    def remove(self, triples: Graph):
        pass
    
    @abstractmethod
    def get(self) -> Graph:
        pass

    @abstractmethod
    def query(self, query: str) -> Graph:
        pass

class OntologyEvent(Enum):
    INSERT = "INSERT"
    DELETE = "DELETE"

class ITripleStoreService(ABC):
    
    __ontology_adaptor: ITripleStorePort
    
    __event_listeners: Dict[tuple, Dict[OntologyEvent, List[tuple[str, Callable]]]]
    
    @abstractmethod
    def subscribe(self, topic: tuple, event_type: OntologyEvent, callback: Callable) -> str:
        """Subscribe to events for a specific topic pattern.

        This method allows subscribing to INSERT or DELETE events that match a specific subject-predicate-object 
        pattern. When matching triples are inserted or deleted, the provided callback will be executed.

        Args:
            topic (tuple): A (subject, predicate, object) tuple specifying the pattern to match.
                Each element can be None to match any value in that position.
            event_type (OntologyEvent): The type of event to subscribe to (INSERT or DELETE)
            callback (Callable): Function to call when matching events occur. Will be called with:
                - event_type: The OntologyEvent that occurred
                - name: Name of the ontology that changed
                - triple: The (subject, predicate, object) triple that matched

        Returns:
            str: A unique subscription ID that can be used to unsubscribe later
        """
        pass
    
    @abstractmethod
    def unsubscribe(self, subscription_id: str):
        """Unsubscribe from events using a subscription ID.

        This method removes a subscription based on its ID, stopping any further callbacks
        for that subscription.

        Args:
            subscription_id (str): The subscription ID returned from a previous subscribe() call
        
        Raises:
            SubscriptionNotFoundError: If no subscription exists with the provided ID

        Returns:
            None
        """
        pass
    
    def __filter_ontology(self, ontology: Graph) -> Graph:
        pass

    @abstractmethod
    def insert(self, triples: Graph):
        """Insert triples from the provided graph into the store.
        
        This method takes a graph of triples and inserts them into the triple store. The triples
        are partitioned and stored by subject to enable efficient subject-based querying.
        
        Args:
            triples (Graph): The RDF graph containing triples to insert
            
        Returns:
            None
        """
        pass
    
    @abstractmethod
    def remove(self, triples: Graph):
        """Remove triples from the provided graph from the store.
        
        This method takes a graph of triples and removes them from the triple store. The triples
        are matched against existing triples and removed where matches are found.
        
        Args:
            triples (Graph): The RDF graph containing triples to remove
            
        Returns:
            None
        """
        pass
    
    @abstractmethod
    def get(self) -> Graph:
        """Get the complete RDF graph from the triple store.
        
        This method retrieves and returns the full RDF graph containing all triples
        stored in the triple store.
        
        Returns:
            Graph: The complete RDF graph containing all stored triples
        """
        pass
    
    @abstractmethod
    def query(self, query: str) -> Graph:
        """Execute a SPARQL query against the triple store.
        
        This method executes the provided SPARQL query string against all triples in the store
        and returns the results as a new RDF graph.
        
        Args:
            query (str): The SPARQL query string to execute against the triple store
            
        Returns:
            Graph: A new RDF graph containing the query results
            
        Example:
            >>> store.query("SELECT ?s WHERE { ?s a owl:Class }")
        """
        pass
        
